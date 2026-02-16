from otree.api import *
import random
import time


doc = """
Stage 2 (BDM) of save-invest experiment
Participants state a certain equivalent (CE) at which they are indifferent between a given lottery and a sure payout.
"""


class C(BaseConstants):
    NAME_IN_URL = 'stage2'
    PLAYERS_PER_GROUP = None
    
    # total rounds is 32 (42 - 10)
    # Now participant.length is used for the round number of stage 2, more flexible with demo
    NUM_ROUNDS = 32 

    # round order will not be randomized 


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    certainty_equivalent = models.FloatField(
        doc="Participant's stated CE for the lottery"
    )
    
    random_price = models.CurrencyField()
    pay_stage = models.IntegerField()
    pay_round = models.IntegerField()
    final_today = models.CurrencyField()
    final_1m = models.CurrencyField()
    
    # Reaction times
    start_time = models.FloatField()
    reaction_time = models.FloatField()
    

# Error Messages for incorrect user inputs
def certainty_equivalent_error_message(self, value):
    # CE must lie between lottery outcomes
    pr = self.round_number - 1
    low = min(self.participant.s2monthA[pr], self.participant.s2monthB[pr])
    high = max(self.participant.s2monthA[pr], self.participant.s2monthB[pr])
    if value < low or value > high:
        return f"Please enter a value between {low} and {high}."


# PAGES

class InstructionsStageTwo(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if player.round_number == 1:
            participant = player.participant
            participant.rts_bdm = []
            
            # randomly select paying round
            # participant.paying_round_stage_2 = random.randint(1, C.NUM_ROUNDS)
            # participant.length created for the demo (shortening the length of the experiment)
            # delete degenerate lotteries
            active_rounds = []
            for r in range(1, participant.length + 1):
                pr = r - 1
                is_degenerate = (
                    participant.s2monthA[pr] == participant.s2monthB[pr]
                    or participant.s2probA[pr] == 1
                )
                if not is_degenerate:
                    active_rounds.append(r)
            participant.s2_active_rounds = active_rounds
            participant.length_active = len(active_rounds)

            if participant.length_active > 0:
                participant.paying_round_stage_2 = random.choice(active_rounds)
                pr = participant.paying_round_stage_2 - 1
                low = min(participant.s2monthA[pr], participant.s2monthB[pr])
                high = max(participant.s2monthA[pr], participant.s2monthB[pr])
                participant.random_price = round(random.uniform(low, high), 2)
            else:
                participant.paying_round_stage_2 = None
                participant.random_price = None

            # randomly select a paying round across 42+32 situations; since the previous code has already drawn a random round from both stage 1 and stage 2, now we are deciding which round to apply (if we were to choose one out of 42+32)
            participant.final_paying_round= random.randint(1, len(participant.probA) + (participant.length_active or 0))


class BdmPage(Page):
    form_model = 'player'
    form_fields = ['certainty_equivalent']

    @staticmethod
    def is_displayed(player: Player):
        participant = player.participant
        if not getattr(participant, 's2_active_rounds', None):
            return False
        if player.round_number not in participant.s2_active_rounds:
            return False
        return player.field_maybe_none('certainty_equivalent') is None

    @staticmethod
    def vars_for_template(player: Player):
        # record start time
        player.start_time = time.time()
        # collect data for each BDM Page
        pr_ = player.round_number - 1
        participant = player.participant
        payment_today = participant.s2savings[pr_]
        monthA = participant.s2monthA[pr_]
        monthB = participant.s2monthB[pr_]
        probA = int(round(participant.s2probA[pr_] * 100))
        probB = int(round(participant.s2probB[pr_] * 100))
        low = min(monthA, monthB)
        high = max(monthA, monthB)
        return dict(
            payment_today=payment_today,
            monthA=monthA,
            monthB=monthB,
            probA=probA,
            probB=probB,
            low=low,
            high=high,
        )

    # store reactions times
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        participant = player.participant
        player.reaction_time = time.time() - player.start_time
        participant.rts_bdm.append(player.reaction_time)

        # final active rounds
        if getattr(participant, 's2_active_rounds', None) and player.round_number == max(participant.s2_active_rounds):
            pr = participant.paying_round_stage_2 - 1 if participant.paying_round_stage_2 else None
            paying_player = player.in_round(participant.paying_round_stage_2) if participant.paying_round_stage_2 else None
            ce = paying_player.certainty_equivalent if paying_player else None
            rp = participant.random_price
            fpr = participant.final_paying_round

            if pr is not None:
                participant.payoff_today_s2 = participant.s2savings[pr]
                if rp is not None and ce is not None and rp < ce:
                    if participant.s2probB[pr] == 0:
                        participant.payoff_one_month_s2 = participant.s2monthA[pr]
                    else:
                        participant.payoff_one_month_s2 = random.choices(
                            [participant.s2monthA[pr], participant.s2monthB[pr]],
                            weights=[participant.s2probA[pr], participant.s2probB[pr]],
                            k=1
                        )[0]
                else:
                    participant.payoff_one_month_s2 = rp
            else:
                participant.payoff_today_s2 = 0
                participant.payoff_one_month_s2 = 0

            if fpr < len(participant.probA) + 1:
                final_today = participant.payoff_today_s1 + 5
                final_1m =  participant.payoff_one_month_s1 + 5
                pay_stage = 1
                pay_round = participant.paying_round
            else:
                final_today = participant.payoff_today_s2 + 5
                final_1m =  participant.payoff_one_month_s2 + 5
                pay_stage = 2
                pay_round = participant.paying_round_stage_2

            player.pay_stage = pay_stage
            player.pay_round = pay_round
            player.final_today = final_today
            player.final_1m = final_1m
            player.random_price = rp



class Results(Page):
    @staticmethod
    def is_displayed(player: Player):
        # return player.round_number == C.NUM_ROUNDS
        participant = player.participant
        if getattr(participant, 's2_active_rounds', None):
            return player.round_number == max(participant.s2_active_rounds)
        return player.round_number == participant.length

    @staticmethod
    def vars_for_template(player: Player):
        participant = player.participant
        pr = (participant.paying_round_stage_2 - 1) if participant.paying_round_stage_2 else None
        paying_player = player.in_round(participant.paying_round_stage_2) if participant.paying_round_stage_2 else None
        ce = paying_player.certainty_equivalent if paying_player else None
        rp = participant.random_price
        fpr = participant.final_paying_round
        # stage2 today payoff
        participant.payoff_today_s2 = participant.s2savings[pr] if pr is not None else 0
        # stage2 one-month payoff via BDM
        if pr is not None and rp is not None and ce is not None and rp < ce:
            # if there is only asset A
            if participant.s2probB[pr] == 0:
                participant.payoff_one_month_s2 = participant.s2monthA[pr]
                executed_asset = 'A'
            else:
                participant.payoff_one_month_s2 = random.choices(
                    [participant.s2monthA[pr], participant.s2monthB[pr]],
                    weights=[participant.s2probA[pr], participant.s2probB[pr]],
                    k=1
                )[0]
                executed_asset = 'A' if participant.payoff_one_month_s2 == participant.s2monthA[pr] else 'B'
            method = 'Lottery'
        else:
            participant.payoff_one_month_s2 = rp if rp is not None else 0
            executed_asset = None
            method = 'Sure amount'

        # stage2 executed assets combination
        if pr is not None:
            exec_probA  = participant.s2probA[pr] * 100
            exec_probB  = participant.s2probB[pr] * 100
            exec_monthA = participant.s2monthA[pr]
            exec_monthB = participant.s2monthB[pr]
        else:
            exec_probA = exec_probB = exec_monthA = exec_monthB = None
        
        # total payoff (stage 1 + stage 2) including fixed payment 
        total_today = participant.payoff_today_s1 + participant.payoff_today_s2 + 5
        total_1m =  participant.payoff_one_month_s1 + participant.payoff_one_month_s2 + 5

        # final payoff (one out of 42+32), including fixed payment
        if fpr < len(participant.probA) + 1: # sectu
            final_today = participant.payoff_today_s1 + 5
            final_1m =  participant.payoff_one_month_s1 + 5
            pay_stage = 1
            pay_round = participant.paying_round
        else:
            final_today = participant.payoff_today_s2 + 5
            final_1m =  participant.payoff_one_month_s2 + 5
            pay_stage = 2
            pay_round = participant.paying_round_stage_2
        
        
        return dict(
            # gets stage 1 results
            payoff_today_s1 = participant.payoff_today_s1,
            paying_asset_s1 = participant.paying_asset,
            payoff_one_month_s1 = participant.payoff_one_month_s1,
            payinground_s1 = participant.paying_round,
            # gets stage 2 results
            payinground_s2 = participant.paying_round_stage_2,
            exec_probA = exec_probA,
            exec_probB = exec_probB,
            exec_monthA = exec_monthA,
            exec_monthB = exec_monthB,
            executed_asset = executed_asset,
            payoff_today_s2 = participant.payoff_today_s2,
            payoff_one_month_s2 = participant.payoff_one_month_s2,
            # BMD results
            random_price = rp,
            ce = ce,
            method = method,
            # total payoff including fixed payment (one from 42 + one from 32)
            total_today = total_today,
            total_1m = total_1m,
            # final payoff including fixed payment (one from 42 + 32)
            final_today = final_today, 
            final_1m = final_1m,
            pay_stage = pay_stage,
            pay_round = pay_round,
        )
        


page_sequence = [
    InstructionsStageTwo,
    BdmPage,
    Results
]
