from enum import Enum


class SharingRole(str, Enum):
    REQUESTER = "requester"
    DATA_OWNER = "data_owner"
    DPO = "dpo"
    SOURCE = "source"
    RECEIVER = "receiver"
