import requests
import logging
import argparse
from datetime import datetime, timedelta, date
from domains.mastodon import send_fixed_slow_zone_toots, send_new_slow_zone_toots, send_updated_slow_zone_toots
from domains.twitter import send_fixed_slow_zone_tweets, send_new_slow_zone_tweets, send_updated_slow_zone_tweets
from domains.slack import send_fixed_slow_zone_slacks, send_new_slow_zone_slacks, send_updated_slow_zone_slacks
from domains.dry import send_fixed_slow_zone_dry, send_new_slow_zone_dry, send_updated_slow_zone_dry
from chalicelib.output import (
    generate_grouped_slow_zone_list,
    generate_post_text_map,
    generate_new_slow_zones_list,
    generate_updated_slow_zones,
)
import sys
from chalicelib.clients import twitter_client, mastodon_client


def run(debug=True, dry_run=True):
    slow_zones = requests.get("https://dashboard.transitmatters.org/static/slowzones/all_slow.json")

    if datetime.fromisoformat(slow_zones.json()["updated_on"]).date() != date.today():
        logging.error("Slow zone data was not updated yet today")
        # exit if issues
        sys.exit(1)

    slow_zones_data = slow_zones.json()["data"]

    grouped_sz_today = generate_grouped_slow_zone_list(slow_zones_data, date.today())
    logging.debug(f"grouped_sz_today: {grouped_sz_today}")

    slowzones_changed_yesterday = generate_updated_slow_zones(slow_zones_data, date.today() - timedelta(days=1))
    logging.info(f"slowzones_changed_yesterday: {slowzones_changed_yesterday}")

    slowzones_ended_yesterday = generate_grouped_slow_zone_list(
        # Slow zones are 1 day behind so we want to check if zones ended two days ago
        slow_zones_data,
        date.today() - timedelta(days=1),
    )
    logging.info(f"slowzones_ended_yesterday: {slowzones_ended_yesterday}")

    slowzones_started_yesterday = generate_new_slow_zones_list(
        # Slow zones take 4 days to be recognized
        slow_zones_data,
        date.today() - timedelta(days=3),
    )
    logging.info(f"slowzones_started_yesterday: {slowzones_started_yesterday}")

    post_text_map = generate_post_text_map(grouped_sz_today)
    logging.debug(f"post_text_map: {post_text_map}")

    # if a dry run, generate slow zone text but do not post
    if dry_run:
        send_new_slow_zone_dry(slowzones_started_yesterday)
        send_fixed_slow_zone_dry(slowzones_ended_yesterday)
        send_updated_slow_zone_dry(slowzones_changed_yesterday)

    # otherwise, post slow zones to socials
    else:
        # try tweeting
        try:
            send_new_slow_zone_tweets(slowzones_started_yesterday, twitter_client)
            send_fixed_slow_zone_tweets(slowzones_ended_yesterday, twitter_client)
            send_updated_slow_zone_tweets(slowzones_changed_yesterday, twitter_client)
        except Exception as e:
            logging.error(f"Failed to tweet: {e}")
        else:
            logging.info("Tweeted successfully")

        # try slacking
        try:
            send_new_slow_zone_slacks(slowzones_started_yesterday)
            send_fixed_slow_zone_slacks(slowzones_ended_yesterday)
            send_updated_slow_zone_slacks(slowzones_changed_yesterday)
        except Exception as e:
            logging.error(f"Failed to send Slack messages: {e}")
        else:
            logging.info("Sent Slack messages successfully")

        # try tooting
        try:
            send_new_slow_zone_toots(slowzones_started_yesterday, mastodon_client)
            send_fixed_slow_zone_toots(slowzones_ended_yesterday, mastodon_client)
            send_updated_slow_zone_toots(slowzones_changed_yesterday, mastodon_client)
        except Exception as e:
            logging.error(f"Failed to toot: {e}")
        else:
            logging.info("Tooted successfully")


if __name__ == "__main__":
    # argument parsing
    parser = argparse.ArgumentParser(description="MBTA Slow Zone Bot")
    parser.add_argument("--dry-run", default=False, action="store_true", help="Runs bot without posting")
    parser.add_argument("--debug", default=False, action="store_true", help="Runs bot with debug logging")
    args = parser.parse_args()
    dry_run = args.dry_run
    debug = args.debug

    # set logging config
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # begin main program execution
    run(debug, dry_run)