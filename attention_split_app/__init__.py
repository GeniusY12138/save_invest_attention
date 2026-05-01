from __future__ import annotations
from otree.api import *
import json
import os
import time
import random

doc = """
Save–Invest as effort timing: participants face TWO separate sessions of a sustained-attention task:
- Today: baseline 45 minutes
- One month later: baseline 45 minutes

In the first stage (today session), participants choose earnings (x dollars for today, y dollars for later).
They do not receive cash immediately; instead, each dollar acts like a 1-minute "time chip" that reduces
the required task time in that session.

So required time is:
- Today task minutes = 45 - final_today
- Later task minutes = 45 - final_1m

The app saves the chosen (x, y) and the implied task minutes to a JSON file keyed by participant label (or code),
so the later session automatically loads the remaining requirement.

This version records attention/accuracy outcomes (without adding time penalties for misses or focus loss).
"""

ALLOC_DIR = os.path.join(os.path.dirname(__file__), 'participant_allocations')
os.makedirs(ALLOC_DIR, exist_ok=True)


def participant_key(participant) -> str:
    """
    Prefer a stable participant label (e.g., Prolific ID / lab subject ID) if provided.
    Fall back to the oTree participant code.
    """
    return (participant.label or participant.code).strip()



def _get_timechip_dollars_from_participant(participant):
    """Fetch (x,y) dollars from earlier stages if available."""
    x = participant.vars.get('final_today', None)
    y = participant.vars.get('final_1m', None)
    x = participant.vars.get('timechip_today_dollars', None)
    y = participant.vars.get('timechip_later_dollars', None)
    if x is None or y is None:
        return None
    try:
        x = float(x)
        y = float(y)
    except Exception:
        return None
    # Clamp to [0, 40] and round to nearest integer minute-dollar.
    x_i = round(max(0, min(C.TOTAL_MINUTES, x)))
    y_i = round(max(0, min(C.TOTAL_MINUTES, y)))
    return x_i, y_i



def alloc_path(key: str) -> str:
    safe = ''.join(ch for ch in key if ch.isalnum() or ch in ('-', '_'))
    return os.path.join(ALLOC_DIR, f'{safe}.json')


def save_allocation(participant, today_dollars: int, later_dollars: int) -> None:
    key = participant_key(participant)
    payload = {
        'key': key,
        'saved_at_unix': time.time(),
        'baseline_minutes_per_session': int(C.TOTAL_MINUTES),
        'today_dollars': today_dollars,
        'later_dollars': later_dollars,
        'today_minutes': C.TOTAL_MINUTES - 2* today_dollars,
        'later_minutes': C.TOTAL_MINUTES - 2* later_dollars,
    }
    with open(alloc_path(key), 'w', encoding='utf-8') as f:
        json.dump(payload, f)
    # Also store in participant.vars so it is available within the same oTree session
    # even if the JSON file path is unavailable (e.g., containerized deployments).
    participant.vars['attention_split_allocation'] = payload



def load_allocation(participant):
    key = participant_key(participant)
    p = alloc_path(key)
    if not os.path.exists(p):
        # Fall back to in-session storage if available.
        return participant.vars.get('attention_split_allocation')
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


class C(BaseConstants):
    NAME_IN_URL = 'attention_split_app'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 2

    # Baseline minutes per session (today AND one-month-later)
    TOTAL_MINUTES = 45

    # Demo preview length
    DEMO_SECONDS = 120

    # Micro-question design
    QUESTION_DEADLINE_MS = 8000  # time to answer after pop-up appears
    INTERVAL_MIN_MS = 10000      # minimum time between pop-ups
    INTERVAL_MAX_MS = 30000      # maximum time between pop-ups

    # No time penalties in this version (we record misses/blur for accuracy/attention measurement).
    MISS_PENALTY_SECONDS = 0
    BLUR_PENALTY_SECONDS = 0

    # Whether consent is shown again in the later session; can be overridden in session config
    SHOW_CONSENT_IN_LATER = False


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    # phase: "today" or "later"
    phase = models.StringField(initial='today')
    later_password = models.StringField(blank=True)

    # Earnings chosen in the first stage ("time chips"): x for today, y for one month later.
    # Each $1 reduces the required minutes in that session by 1 minute.
    timechip_today_dollars = models.FloatField(min=0, max=C.TOTAL_MINUTES, blank=True)
    timechip_later_dollars = models.FloatField(min=0, max=C.TOTAL_MINUTES, blank=True)
    today_dollars = models.FloatField(min=0, max=C.TOTAL_MINUTES, blank=True)
    later_dollars = models.FloatField(min=0, max=C.TOTAL_MINUTES, blank=True)

    # Convenience fields for exports/clarity (derived from dollars)
    today_minutes = models.FloatField(min=0, max=C.TOTAL_MINUTES, blank=True)
    later_minutes = models.FloatField(min=0, max=C.TOTAL_MINUTES, blank=True)

    # Task outcomes (for whichever session this run corresponds to)
    assigned_task_seconds = models.FloatField(initial=0)
    completed_task_seconds = models.FloatField(initial=0)
    makeup_seconds = models.FloatField(initial=0)

    missed_questions = models.FloatField(initial=0)
    blur_events = models.FloatField(initial=0)
    incorrect_answers = models.FloatField(initial=0)
    answered_questions = models.FloatField(initial=0)
    total_questions = models.FloatField(initial=0)

    # Accuracy metrics (computed server-side after the task page submits)
    correct_answers = models.FloatField(initial=0)
    accuracy_rate = models.FloatField(initial=0)

    # Raw logs for audit/attention diagnostics (JSON string)
    task_log_json = models.LongStringField(blank=True)

    # Comprehension checks
    understood_total = models.BooleanField(
        choices=[[True, 'Yes'], [False, 'No']],
        label='Do you understand that the baseline task length is 40 minutes today AND 40 minutes one month later?'
    )
    understood_split = models.BooleanField(
        choices=[[True, 'Yes'], [False, 'No']],
        label='Do you understand that your earnings (x today, y later) reduce task time in the corresponding session: today time = 40 − x, later time = 40 − y?'
    )


def creating_session(subsession: Subsession):
    for p in subsession.get_players():
        phase = subsession.session.config.get('phase', 'today')
        if phase not in ('today', 'later'):
            phase = 'today'
        p.phase = phase



class Instructions(Page):

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player: Player):
        xy = _get_timechip_dollars_from_participant(player.participant) if player.session.config.get('use_external_timechips', False) else None
        if xy is None:
            x, y = 0, 0
        else:
            x, y = xy
        today_minutes = C.TOTAL_MINUTES - 2* x
        later_minutes = C.TOTAL_MINUTES - 2* y
        return dict(
            total_minutes=C.TOTAL_MINUTES,
            demo_seconds=C.DEMO_SECONDS,
            timechip_today_dollars=x,
            timechip_later_dollars=y,
            today_dollars=x,
            later_dollars=y,
            today_minutes=today_minutes,
            later_minutes=later_minutes,
            interval_min=C.INTERVAL_MIN_MS,
            interval_max=C.INTERVAL_MAX_MS,
            deadline_ms=C.QUESTION_DEADLINE_MS,)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        xy = _get_timechip_dollars_from_participant(player.participant) if player.session.config.get('use_external_timechips', False) else None
        if xy is None:
            x, y = 0, 0
        else:
            x, y = xy
        player.timechip_today_dollars = x
        player.timechip_later_dollars = y
        player.today_dollars = x
        player.later_dollars = y
        player.today_minutes = C.TOTAL_MINUTES - 2* player.today_dollars
        player.later_minutes = C.TOTAL_MINUTES - 2* player.later_dollars
        save_allocation(player.participant, player.today_dollars, player.later_dollars)


class Demo(Page):



    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player: Player):
        seed = (player.participant.id_in_session * 104729 + 12345) % 2147483647
        return dict(
            demo_seconds=C.DEMO_SECONDS,
            seed=seed,
            interval_min=C.INTERVAL_MIN_MS,
            interval_max=C.INTERVAL_MAX_MS,
            deadline_ms=C.QUESTION_DEADLINE_MS,
        )
    

class LaterWall(Page):
    form_model = 'player'
    form_fields = ['later_password']

    @staticmethod
    def is_displayed(player: Player):
        # Only show before the later attention section (round 2)
        return player.round_number == 2

    @staticmethod
    def error_message(player: Player, values):
        entered = (values.get('later_password') or '').strip()
        expected = str(player.session.config.get('later_wall_password', '')).strip()
        if entered != expected:
            return "Incorrect password."



class Task(Page):
    form_model = 'player'
    form_fields = [
        'task_log_json',
        'completed_task_seconds',
        'makeup_seconds',
        'missed_questions',
        'blur_events',
        'incorrect_answers',
        'answered_questions',
        'total_questions',
    ]


    @staticmethod
    def vars_for_template(player: Player):
        # Round 1 = "today", Round 2 = "later"
        if player.round_number == 1:
            player.phase = 'today'
            if player.session.config.get('use_external_timechips', False):
                xy = _get_timechip_dollars_from_participant(player.participant)
                if xy is None:
                    x, y = 0, 0
                else:
                    x, y = xy
                player.timechip_today_dollars = x
                player.timechip_later_dollars = y
                player.today_dollars = x
                player.later_dollars = y
                player.today_minutes = C.TOTAL_MINUTES - 2*x
                player.later_minutes = C.TOTAL_MINUTES - 2*y
                save_allocation(player.participant, x, y)
            else:
                x = float(player.today_dollars or 0)
                y = float(player.later_dollars or 0)
                player.today_minutes = C.TOTAL_MINUTES - 2*x
                player.later_minutes = C.TOTAL_MINUTES - 2*y
            minutes = float(player.today_minutes)
        else:
            player.phase = 'later'
            alloc = load_allocation(player.participant)
            if alloc:
                player.today_dollars = float(alloc.get('today_dollars', 0))
                player.later_dollars = float(alloc.get('later_dollars', 0))
                player.today_minutes = float(alloc.get('today_minutes', C.TOTAL_MINUTES))
                player.later_minutes = float(alloc.get('later_minutes', C.TOTAL_MINUTES))
                player.timechip_today_dollars = float(alloc.get('timechip_today_dollars', 0))
                player.timechip_later_dollars = float(alloc.get('timechip_later_dollars', 0))
            else:
                player.today_dollars = 0
                player.later_dollars = 0
                player.today_minutes = C.TOTAL_MINUTES
                player.later_minutes = C.TOTAL_MINUTES
                player.timechip_today_dollars = 0
                player.timechip_later_dollars = 0
            minutes = float(player.later_minutes)

        assigned_seconds = int(minutes * 60)
        player.participant.vars['assigned_task_seconds'] = int(assigned_seconds)

        player.assigned_task_seconds = assigned_seconds

        seed = (player.participant.id_in_session * 104729 + 77777 + player.round_number) % 2147483647
        return dict(
            phase=player.phase,
            baseline_minutes=C.TOTAL_MINUTES,
            timechip_today_dollars=player.timechip_today_dollars,
            timechip_later_dollars=player.timechip_later_dollars,
            today_dollars=player.today_dollars,
            later_dollars=player.later_dollars,
            today_minutes=player.today_minutes,
            later_minutes=player.later_minutes,
            assigned_seconds=assigned_seconds,
            interval_min_ms=C.INTERVAL_MIN_MS,
            interval_max_ms=C.INTERVAL_MAX_MS,
            question_deadline_ms=C.QUESTION_DEADLINE_MS,
            seed=seed,
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # No time penalties; just record what happened.
        if player.answered_questions is None:
            player.answered_questions = 0
        if player.incorrect_answers is None:
            player.incorrect_answers = 0

        total = int(player.total_questions or 0)

        correct = int(player.answered_questions) - int(player.incorrect_answers)
        if correct < 0:
            correct = 0
        player.correct_answers = correct
        player.accuracy_rate = (correct / total) if total > 0 else 0.0

        player.completed_task_seconds = int(player.assigned_task_seconds or 0)
        player.makeup_seconds = 0




class End(Page):
    @staticmethod
    def is_displayed(player: Player):
        return True



    @staticmethod
    def vars_for_template(player: Player):
        if player.phase == 'today':
            x = player.today_dollars or 0
            y = player.later_dollars or 0
            today_m = player.today_minutes or (C.TOTAL_MINUTES - 2*x)
            later_m = player.later_minutes or (C.TOTAL_MINUTES - 2*y)
        else:
            x = player.today_dollars or 0
            y = player.later_dollars or 0
            today_m = player.today_minutes or C.TOTAL_MINUTES
            later_m = player.later_minutes or C.TOTAL_MINUTES

        return dict(
            accuracy_rate_str=f"{(player.accuracy_rate or 0.0):.3f}",
            phase=player.phase,
            baseline_minutes=C.TOTAL_MINUTES,
            timechip_today_dollars=x,
            timechip_later_dollars=y,
            today_dollars=x,
            later_dollars=y,
            today_minutes=today_m,
            later_minutes=later_m,
        )

page_sequence = [Instructions, Demo, LaterWall, Task, End]
