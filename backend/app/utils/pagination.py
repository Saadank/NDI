import math


def get_pagination_data(limit: int, page: int, total: int) -> dict:
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    has_next_page = page < total_pages
    has_previous_page = page > 1

    return {
        "pagination": {
            "total_pages": total_pages,
            "next_page": page + 1 if has_next_page else None,
            "previous_page": page - 1 if has_previous_page else None,
            "page": page,
            "limit": limit,
        },
    }
