from enum import Enum


class ProductSlug(str, Enum):
    DATA_SHARING = "data_sharing"
    DATA_QUALITY = "data_quality"
    NDMO = "ndmo"
    DSR = "dsr"
