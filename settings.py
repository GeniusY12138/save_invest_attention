from os import environ

SESSION_CONFIGS = [
    dict(
        name='save_invest_allinone',
        display_name='Save–Invest + Attention (Today then Later)',
        app_sequence=['stage1', 'stage2', 'attention_split_app'],
        num_demo_participants=1,
        use_external_timechips=True,
        show_consent_in_later=False,
        later_wall_password='admin',
    ),
]

# Inherited by all SESSION_CONFIGS unless overridden there.
# You can access these as self.session.config['participation_fee'], etc.
SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00,
    participation_fee=5.00,
    doc="",
)

PARTICIPANT_FIELDS = [
    'order',
    'round_order',
    'paying_round',
    'paying_asset_number',
    'paying_order_s2',
    'paying_choice_number_s2',
    'paying_asset_s2',
    'paying_round_order',
    'paying_asset',
    'payoff_one_month_s1',
    'payoff_today_s1',
    'payoff_one_month_s2',
    'payoff_today_s2',
    'monthA',
    'monthB',
    'probA',
    'probB',
    'savings',
    's2probA',
    's2probB',
    's2savings',
    's2monthA',
    's2monthB',
    'paying_round_stage_2',
    'paying_row',
    'rts_invest',
    'rts_save',
    'rts_bdm',
    'length',
    'random_price',
    'final_paying_round',
    's2_active_rounds',
    'length_active',
]

SESSION_FIELDS = []

# ISO-639 code (e.g. en, de, fr, ja, ko, zh-hans)
LANGUAGE_CODE = 'en'

# e.g. EUR, GBP, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = False

ROOMS = [
    dict(
        name='CELSS_lab',
        display_name='CELSS Lab',
        participant_label_file='_rooms/test_participant_file.txt',
        use_secure_urls=False,
    ),
]

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """ """

SECRET_KEY = '5455770345824'

# oTree requires this; keep it if you already have it elsewhere.
# If your project already defines INSTALLED_APPS, don’t duplicate—just ensure 'otree' is in it.
INSTALLED_APPS = ['otree']
