import re
from functools import lru_cache

from database import get_connection, init_db


REMOVE_WORDS = (
    "\uc544\ud30c\ud2b8",
    "APT",
    "apt",
    "\uc8fc\uc0c1\ubcf5\ud569",
    "\ub2e8\uc9c0",
)


NORMALIZE_REPLACEMENTS = (
    ("\uc5d0\uc2a4\ucf00\uc774", "sk"),
    ("\uc5e0\ubca8\ub9ac", "\uc5e0\ubc38\ub9ac"),
    ("\ubdf0", "view"),
    ("VIEW", "view"),
    ("View", "view"),
)


MANUAL_COMPLEX_NAME_ALIASES = {
    ("\uc1a1\ud30c\uad6c", "\uc7a5\uc9c0\ub3d9", "\uc704\ub840\uc2e0\ub3c4\uc2dc\uc1a1\ud30c\ud478\ub974\uc9c0\uc624"): "\uc704\ub840 \uc1a1\ud30c\ud478\ub974\uc9c0\uc624",
    ("\uac15\uc11c\uad6c", "\ub9c8\uace1\ub3d9", "\ub9c8\uace1\uc5e0\ubca8\ub9ac(15\ub2e8\uc9c0)"): "\ub9c8\uace1\uc5e0\ubc38\ub9ac15\ub2e8\uc9c0",
    ("\uc601\ub4f1\ud3ec\uad6c", "\ub2f9\uc0b0\ub3d95\uac00", "\ub2f9\uc0b0\ud6a8\uc1311\ucc28"): "\ub2f9\uc0b0\ub3d91\ucc28\ud6a8\uc131\uc544\ud30c\ud2b8",
    ("\ub3d9\uc791\uad6c", "\uc0c1\ub3c4\ub3d9", "\uc0c1\ub3c4\ub3d9\ub798\ubbf8\uc5481\ucc28"): "\uc0c1\ub3c4\ub798\ubbf8\uc5481\ucc28",
    ("\uc740\ud3c9\uad6c", "\uc218\uc0c9\ub3d9", "DMCSK\ubdf0\uc544\uc774\ud30c\ud06c\ud3ec\ub808"): "DMC SKVIEW \uc544\uc774\ud30c\ud06c\ud3ec\ub808",
    ("\uc601\ub4f1\ud3ec\uad6c", "\uc2e0\uae38\ub3d9", "\uc6b0\uc1311"): "\uc2e0\uae381\ucc28\uc6b0\uc131\uc544\ud30c\ud2b8",
}


MANUAL_HOUSEHOLD_COUNTS = {
    ("\uac15\ub0a8\uad6c", "\ub3c4\uace1\ub3d9", "\ud558\uc774\ud398\ub9ac\uc628"): 71,
}


def normalize_name(value):
    text = value or ""
    for old, new in NORMALIZE_REPLACEMENTS:
        text = text.replace(old, new)
    for word in REMOVE_WORDS:
        text = text.replace(word, "")
    return re.sub(r"[^0-9A-Za-z\uac00-\ud7a3]", "", text).lower()


def normalize_jibun(value):
    return re.sub(r"[^0-9-]", "", value or "")


def address_has_jibun(address, dong_name, jibun):
    if not address or not dong_name or not jibun:
        return False
    normalized_jibun = normalize_jibun(jibun)
    if not normalized_jibun:
        return False
    return re.search(rf"{re.escape(dong_name)}\s+{re.escape(normalized_jibun)}(\D|$)", address) is not None


def remove_location_words(value, gu_name, dong_name):
    text = value
    for word in (gu_name, dong_name, (dong_name or "").replace("\ub3d9", "")):
        if word:
            text = text.replace(word, "")
    return text


def character_bigram_score(left, right):
    if not left or not right:
        return 0
    if left == right:
        return 100
    if left in right or right in left:
        return 70 + min(len(left), len(right))
    if len(left) < 2 or len(right) < 2:
        return 0

    left_bigrams = {left[index : index + 2] for index in range(len(left) - 1)}
    right_bigrams = {right[index : index + 2] for index in range(len(right) - 1)}
    overlap = len(left_bigrams & right_bigrams)
    if not overlap:
        return 0
    return int(100 * (2 * overlap) / (len(left_bigrams) + len(right_bigrams)))


def name_similarity_score(target, candidate_name, gu_name, dong_name):
    candidate = normalize_name(candidate_name)
    if not target or not candidate:
        return 0

    score = character_bigram_score(target, candidate)

    stripped_target = normalize_name(remove_location_words(target, gu_name, dong_name))
    stripped_candidate = normalize_name(remove_location_words(candidate, gu_name, dong_name))
    score = max(score, character_bigram_score(stripped_target, stripped_candidate))

    return score


def get_household_count_for_trade(row):
    return get_household_count(
        row["gu_name"],
        row["umd_nm"],
        row["apt_name"],
        row["jibun"],
    )


@lru_cache(maxsize=20000)
def get_household_count(gu_name, dong_name, apt_name, jibun=None):
    init_db()
    trade_key = (gu_name, dong_name, apt_name)

    manual_count = MANUAL_HOUSEHOLD_COUNTS.get(trade_key)
    if manual_count is not None:
        return manual_count

    target = normalize_name(apt_name)
    alias_name = MANUAL_COMPLEX_NAME_ALIASES.get(trade_key)
    alias_target = normalize_name(alias_name)

    with get_connection() as conn:
        candidates = conn.execute(
            """
            SELECT household_count, kapt_name, address, road_address
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
        raw_candidate_name = candidate["kapt_name"]
        candidate_name = normalize_name(raw_candidate_name)
        if not candidate_name:
            continue

        same_jibun = address_has_jibun(candidate["address"], dong_name, jibun)
        score = name_similarity_score(target, raw_candidate_name, gu_name, dong_name)
        if alias_target and alias_target == candidate_name:
            score = 200

        if same_jibun and score >= 28:
            score += 250
        elif score < 72:
            score = 0

        if score > best_score:
            best_score = score
            best_count = candidate["household_count"]

    return best_count
