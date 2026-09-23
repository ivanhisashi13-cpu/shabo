"""One-off maintenance: clear all stats/leaderboard data, keep accounts.

Resets lifetime and seasonal counters on ``users`` and drops the archived
season standings plus the runtime season pointer. Account credentials and
profile fields (user_id, password, nickname, avatar) are left untouched.
"""

import os
import sqlite3


def main() -> None:
	"""Wipe stats while preserving accounts."""
	db_path = os.getenv("SHABO_DB_PATH", "/data/shabo.db")
	conn = sqlite3.connect(db_path)
	try:
		cur = conn.cursor()
		cur.execute(
			"UPDATE users SET "
			"games_played = 0, "
			"games_won = 0, "
			"shabo_count = 0, "
			"best_multi_score = NULL, "
			"season_key = NULL, "
			"season_wins = 0, "
			"season_shabo = 0, "
			"season_low = NULL"
		)
		users_reset = cur.rowcount
		cur.execute("DELETE FROM season_records")
		records_cleared = cur.rowcount
		cur.execute("DELETE FROM app_state")
		state_cleared = cur.rowcount
		conn.commit()
		print(f"users_reset={users_reset} season_records_cleared={records_cleared} app_state_cleared={state_cleared}")
	finally:
		conn.close()


if __name__ == "__main__":
	main()
