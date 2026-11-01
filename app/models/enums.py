"""Enumerations shared by models, schemas and services. Values match the dashboard's TypeScript types."""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    OPS = "ops"
    FINANCE = "finance"
    MERCHANT_OWNER = "merchant_owner"
    MERCHANT_STAFF = "merchant_staff"

    @property
    def is_admin(self) -> bool:
        return self in ADMIN_ROLES


ADMIN_ROLES = frozenset({Role.SUPER_ADMIN, Role.OPS, Role.FINANCE})
MERCHANT_ROLES = frozenset({Role.MERCHANT_OWNER, Role.MERCHANT_STAFF})


class MerchantStatus(StrEnum):
    PENDING_REVIEW = "Pending Review"
    ACTIVE = "Active"
    SUSPENDED = "Suspended"


class PayoutSchedule(StrEnum):
    MANUAL = "Manual"
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"


class PayoutMethod(StrEnum):
    MPESA = "M-Pesa"
    TILL = "Till"
    PAYBILL = "Paybill"
    BANK = "Bank transfer"


class PaymentStatus(StrEnum):
    INITIATED = "Initiated"
    PENDING = "Pending"
    SUCCESSFUL = "Successful"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    REVERSED = "Reversed"
    REFUNDED = "Refunded"
    UNMATCHED = "Unmatched"


class Attribution(StrEnum):
    MATCHED = "Matched"
    UNMATCHED = "Unmatched"
    MANUAL = "Manual"


class Channel(StrEnum):
    STK = "STK Push"
    PAYMENT_LINK = "Payment Link"
    TILL = "Till"


class CallbackKind(StrEnum):
    STK = "stk"
    C2B_VALIDATION = "c2b_validation"
    C2B_CONFIRMATION = "c2b_confirmation"
    B2C = "b2c"
    B2B = "b2b"
    TIMEOUT = "timeout"


class LedgerKind(StrEnum):
    COLLECTION = "collection"          # + gross customer payment
    FEE = "fee"                        # - Oryne transaction fee
    REFUND = "refund"                  # - refund / reversal of a collection
    FEE_REVERSAL = "fee_reversal"      # + fee returned on a refund, if policy allows
    PAYOUT = "payout"                  # - amount sent to the merchant (net)
    PAYOUT_FEE = "payout_fee"          # - Oryne payout fee
    PAYOUT_REVERSAL = "payout_reversal"  # + failed payout returned to balance
    SMS_TOPUP = "sms_topup"            # - SMS credit bought from the available balance
    ADJUSTMENT = "adjustment"          # +/- manual correction, always with a memo


class PayoutStatus(StrEnum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class Remittance(StrEnum):
    B2C = "B2C"
    B2B = "B2B"
    MANUAL = "Manual"


class InitiatedBy(StrEnum):
    MERCHANT = "Merchant"
    SCHEDULED = "Scheduled"
    ADMIN = "Admin"


class ApiKeyKind(StrEnum):
    SECRET = "secret"            # server-to-server; can create payments
    PUBLISHABLE = "publishable"  # browser checkout snippet; restricted to the merchant's domains


class AccessRequestStatus(StrEnum):
    NEW = "New"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class ExpenseStatus(StrEnum):
    PAID = "Paid"
    PENDING = "Pending"
    OVERDUE = "Overdue"
