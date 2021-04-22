from decimal import *

MONEY_GENERATION_MODIFIER = 1.1
TRANSACTION_FEE = Decimal(0.001)
TTL = 5  # Number of times the an item in the checklist is posted again to the network
INTERVAL_TIME = 4  # Number of seconds between sending (same) messages
RESEND_PENDING_ITEMS_TIME = 10
USPWR_LATE_SEND_TIMEOUT = 10

MISSING_TXN_RESEND_TIMEOUT = 30
