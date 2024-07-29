from datetime import timedelta


def format_duration(seconds):
    duration_td = timedelta(seconds=seconds)
    hours, remainder = divmod(duration_td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)} hours {int(minutes)} minutes {int(seconds)} seconds"