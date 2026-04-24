import re

from database import get_connection, init_db


REMOVE_WORDS = (
    "\uc544\ud30c\ud2b8",
    "APT",
    "apt",
    "\uc8fc\uc0c1\ubcf5\ud569",
    "\ub2e8\uc9c0",
)


def normalize_name(value):
    text = value or ""
    for word in REMOVE_WORDS:
        text = text.replace(word, "")
    return re.sub(r"[^0-9A-Za-z\uac00-\ud7a3]", "", text).lower()


def get_household_count_for_trade(row):
    init_db()
    apt_name = row["apt_name"]
    gu_name = row["gu_name"]
    dong_name = row["umd_nm"]
    target = normalize_name(apt_name)

    with get_connection() as conn:
        candidates = conn.execute(
            """
            SELECT household_count, kapt_name
            FROM apartment_complexes
            WHERE household_count IS NOT NULL
              AND as2 = :gu_name
              AND (:dong_name IS NULL OR as3 = :dong_name)
            """,
            {"gu_name": gu_name, "dong_name": dong_name},
        ).fetchall()

    best_count = None
    best_score = 0
    for candidate in candidates:
        candidate_name = normalize_name(candidate["kapt_name"])
        if not candidate_name:
            continue

        score = 0
        if target == candidate_name:
            score = 100
        elif target in candidate_name or candidate_name in target:
            score = min(len(target), len(candidate_name))

        if score > best_score:
            best_score = score
            best_count = candidate["household_count"]

    return best_count
