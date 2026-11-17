from datetime import datetime
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")

now = datetime.now(WARSAW_TZ)

print("Current Warsaw time:", now)
print("UTC offset:", now.strftime("%z"))
print("Timezone:", now.tzinfo)
