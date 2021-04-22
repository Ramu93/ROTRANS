from decimal import Decimal, ROUND_HALF_EVEN

GENESIS = b'Genesis'

CKPT_CREATION_TIME_TH = 600
CKPT_PARTICIPATION_STAKE_TH = 10
# fee/reward generation constant
ALPHA = Decimal(1.5).quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN)

FEE_THRESHOLD = Decimal(0.0000001)
REWARD = Decimal(1)
CKPT_PRIORITY_RCV_TIMEOUT = 30.0
PROPOSAL_HASH_RCV_TIME = 20.0
CKPT_PROPOSAL_RCV_TIMEOUT = 60.0
PROPOSAL_TXNS_RCV_TIME = 30.0

TRANSITION_BUFFER_TIME = 5.0
MAJORITY_VOTE_POST_PERIOD = 3.5

STALEMATE_TIME = 30.0
MISSING_VOTES_REQUEST_TIME = 5.0
VOTES_CHECKLIST_TIME = 4.0
REQUESTED_VOTE_RESPONSE_TIME = 4.0
VOTE_DISTRIB_EVAL_TIME = 2.0
PREV_VOTES_CHECKLIST_BROADCAST = 8.0
VOTE_TRY_TIME_OUT = 6.0

CKPT_SYNC_DAG_CHECK = 3.0
CKPT_SYNC_CHECKLIST = 16.0
CKPT_SYNC_FETCH = 4.0
CKPT_SYNC_RESPONSE = 5.0
