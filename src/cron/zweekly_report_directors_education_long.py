import json
import boto3
import requests
from supabase import create_client, Client
from datetime import datetime, timezone
import os

REGION = "ap-southeast-1"
REPORT_PATH = "/tmp/directors_education_report.txt"


def get_secrets():
    client = boto3.client("secretsmanager", region_name=REGION)

    discord_secret = json.loads(
        client.get_secret_value(SecretId="discord_keys")["SecretString"]
    )
    supabase_secret = json.loads(
        client.get_secret_value(SecretId="supabase_keys")["SecretString"]
    )

    return {
        "DISCORD_WEBHOOK_CHANNEL_THLC_BOT": discord_secret.get("DISCORD_WEBHOOK_CHANNEL_THLC_BOT"),
        "SUPABASE_URL": supabase_secret.get("SUPABASE_URL"),
        "SUPABASE_KEY": supabase_secret.get("SUPABASE_KEY"),
    }


SECRETS = get_secrets()


def build_directors_education_report(directors, courses) -> str:
    """Builds a report of all directors and their education progress."""

    utc_now = datetime.now(timezone.utc)
    timestamp = utc_now.strftime("%Y-%m-%d %H:%M:%S TCT")

    if not directors or not courses:
        return f"No data found.\nGenerated at: {timestamp}"

    # Column widths
    code_width = 7
    course_name_width = max(len(c["course_name"]) for c in courses) + 5
    status_width = 5  # for ✔/✖

    lines = [
        "=" * 80,
        " " * 10 + "DIRECTORS EDUCATION REPORT",
        f"Generated at: {timestamp}",
        "=" * 80,
        ""
    ]

    # Map courses by course_id for quick lookup
    # (we'll iterate courses in stable order)
    courses_sorted = sorted(courses, key=lambda c: c.get("course_code", ""))

    # For each director produce their section
    for director in directors:
        lines.append("")  # blank line between directors
        lines.append("")  

        # safe extraction of company fields
        company_name = None
        company_acronym = None
        comp = director.get("company") or {}
        if isinstance(comp, dict):
            company_name = comp.get("company_name") or director.get("company_name")
            company_acronym = comp.get("company_acronym") or director.get("company_acronym")
        # fallback to top-level keys if present
        if not company_name:
            company_name = director.get("company_name")
        if not company_acronym:
            company_acronym = director.get("company_acronym")

        # Build header safely (avoid nested f-string quoting issues)
        director_name = director.get("director_name") or director.get("name") or f"Director {director.get('torn_user_id')}"
        torn_id = director.get("torn_user_id")
        comp_id = director.get("company_id") or (comp.get("company_id") if isinstance(comp, dict) else None)

        company_display = f"Company {comp_id}"
        if company_name:
            if company_acronym:
                company_display = f"{company_name} ({company_acronym})"
            else:
                company_display = company_name

        header = f"Director: {director_name} [{torn_id}] : {company_display} [{comp_id}]"
        lines.append(header)
        lines.append("")  # blank line after header

        # Table header
        table_header = f"{'Code':<{code_width}}  {'Course Name':<{course_name_width}}  {'Status':^{status_width}}"
        lines.append(table_header)
        lines.append("-" * len(table_header))

        # Map of completed course_ids for this director
        completed_ids = {c.get("course_id") for c in director.get("completed_courses", [])}

        # Loop over all reference courses (sorted)
        for c in courses_sorted:
            course_id = c.get("course_id")
            course_code = c.get("course_code", "")[:code_width]  # assume exact 7 chars per your note
            course_name = c.get("course_name", "")
            completed = "✅" if course_id in completed_ids else "❌"
            lines.append(
                f"{course_code:<{code_width}}  {course_name:<{course_name_width}}  {completed:^{status_width}}"
            )

        lines.append("")  # blank line after director

    lines.append("=" * 80)
    return "\n".join(lines)


def save_report_to_file(report_text: str, file_path: str):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"✅ Report written to {file_path}")
    except Exception as e:
        print(f"❌ Error writing report: {e}")


def send_discord_file(webhook_url: str, file_path: str, message: str = None):
    if not webhook_url:
        print("⚠️ Discord webhook URL missing.")
        return

    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {"content": message or "📊 Directors education report attached."}
            response = requests.post(url=webhook_url, data=data, files=files, timeout=30)

        if response.status_code in (200, 204):
            print("✅ Report successfully sent to Discord.")
        else:
            print(f"⚠️ Discord returned {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")


def lambda_handler(event=None, context=None):
    supabase: Client = create_client(SECRETS["SUPABASE_URL"], SECRETS["SUPABASE_KEY"])

    # Fetch discord channel for group ops
    try:
        channels = supabase.table("discord_company_channels").select("*").execute().data
    except Exception as e:
        print(f"❌ Error fetching discord channels: {e}")
        return

    discord_webhook_url = None
    for ch in channels:
        if ch.get("company_id", 0) == 0:
            discord_webhook_url = ch.get("discord_webhook_url")
            break

    if not discord_webhook_url:
        print("⚠️ No group ops discord webhook found.")
        return

    # Fetch directors with nested company info
    try:
        directors_query = (
            supabase.table("directors")
            .select("torn_user_id, director_name, company_id, company:company(company_id, company_name, company_acronym)")
            .execute()
        )
        directors_raw = directors_query.data or []
    except Exception as e:
        print(f"❌ Error fetching directors: {e}")
        return

    if not directors_raw:
        print("⚠️ No directors found.")
        return

    # Flatten directors: ensure company object present and standard keys
    directors = []
    for d in directors_raw:
        comp = d.get("company") or {}
        directors.append({
            "torn_user_id": d.get("torn_user_id"),
            "director_name": d.get("director_name"),
            "company_id": comp.get("company_id") or d.get("company_id"),
            "company_name": comp.get("company_name"),
            "company_acronym": comp.get("company_acronym"),
            # we'll attach completed_courses later
            "completed_courses": []
        })

    # Fetch all courses
    try:
        courses_query = supabase.table("ref_education").select("course_id, course_code, course_name").execute()
        courses = courses_query.data or []
    except Exception as e:
        print(f"❌ Error fetching courses: {e}")
        return

    if not courses:
        print("⚠️ No courses found.")
        return

    # Fetch completed education (only completed rows)
    try:
        completed_query = supabase.table("director_education").select("torn_user_id, course_id").eq("completed", True).execute()
        completed_rows = completed_query.data or []
    except Exception as e:
        print(f"❌ Error fetching completed education: {e}")
        return

    # Map completed course IDs by torn_user_id
    completed_map = {}
    for row in completed_rows:
        completed_map.setdefault(row["torn_user_id"], []).append({"course_id": row["course_id"]})

    # Attach completed courses to each director
    for director in directors:
        director["completed_courses"] = completed_map.get(director["torn_user_id"], [])

    # Build report
    report_text = build_directors_education_report(directors, courses)
    save_report_to_file(report_text, REPORT_PATH)

    # Send report to Discord
    send_discord_file(
        discord_webhook_url,
        REPORT_PATH,
        f"📄 Directors Education Report ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    )

    print("✅ Directors education report completed successfully.")


if __name__ == "__main__":
    lambda_handler()
