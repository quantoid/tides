import altair as alt
import pandas as pd

# Colours used on chart.
colour_night = "#d1d3ea"  # lavender
colour_best = "#30a639"  # green
colour_worst = "#c0141b"  # red
colour_water = "#bcdaf2"  # blue
colour_days = "#767676"  # grey

time_zone = "Australia/Brisbane"
time_format = "%I:%M %p on %a %d %b"


def darkness(sun):
    """
    Rectangle chart of dark periods between daylight periods.
    """
    # Get dusk on one day and dawn on the next.
    night = pd.DataFrame().reindex_like(sun)
    night['dusk'] = sun['dusk']
    night['dawn'] = sun['dawn'].shift(-1)
    night = night[night['dawn'].notnull()]
    domain = [night['dusk'].min(), night['dawn'].max()]
    return alt.Chart(night).mark_rect(opacity=0.6, color=colour_night, clip=True).encode(
        x=alt.X(
            "dusk:T",
            # Have to convert pd.Timestamp to alt.DateTime for temporal domain.
            scale=alt.Scale(domain=[convert_dt(t) for t in domain]),
        ),
        x2="dawn:T",
        tooltip=[
            alt.Tooltip("dusk", format=time_format),
            alt.Tooltip("dawn", format=time_format),
        ]
    )


def convert_dt(dt):
    return alt.DateTime(
        year=dt.year,
        month=dt.month,
        date=dt.day,
        hours=dt.hour,
        minutes=dt.minute,
    )


def days(sun):
    """
    Show label for each day on chart at noon.
    """
    return alt.Chart(sun[1:-1]).mark_text(
        clip=False,
        color=colour_days,
        dy=-12,
        fontSize=16,
    ).encode(
        x="noon:T",
        y=alt.value(0),
        text=alt.Text("noon:T", format="%a %d %b"),
    )


def heights(tides):
    """
    Area chart of tide heights.
    """
    return alt.Chart(tides).mark_area(
        clip=True,
        line=False,
        color=colour_water,
        opacity=0.5,
    ).encode(
        x=alt.X(
            "time:T",
            title=None,
            axis=alt.Axis(grid=False, ticks=True, labelAngle=-45),
        ),
        y=alt.Y(
            "height:Q",
            title="Tide Height (m)",
            axis=alt.Axis(grid=True, tickCount=5),
            scale=alt.Scale(zero=True),
        ),
        tooltip=[
            alt.Tooltip("time", format=time_format),
            alt.Tooltip("height", format=".1f"),
        ],
    )


def curve(tides, safe):
    """
    Line chart of tide height coloured by safety.
    """
    # Hide parts of line that are safe/unsafe.
    line = tides[['time', 'height', 'safe']].copy()
    hide = ~line['safe'] if safe else line['safe']
    line.loc[hide, 'height'] = None
    # Show coloured parts of line that are not hidden.
    return alt.Chart(line).mark_line(
        clip=True,
        color=colour_best if safe else colour_worst,
    ).encode(
        x="time:T",
        y="height:Q",
        tooltip=[
            alt.Tooltip("time", format=time_format),
            alt.Tooltip("height", format=".1f"),
        ],
    )


def periods(low, high):
    """
    Labels giving safe driving periods.
    """
    time_only = "%I:%M%p"
    safer = low[low['earliest'].notnull() & low['latest'].notnull()].copy()
    safer['period'] = (
        "✓ " + safer['earliest'].dt.strftime(time_only).str.lstrip('0')
        + " - " + safer['latest'].dt.strftime(time_only).str.lstrip('0')
    ).str.lower()
    # Find maximum height to show times above that
    # using steps to get positions of text labels.
    highest = high['height'].max()
    steps = highest * 0.11
    # Rank tides by time of day and position labels with the earliest above the latest.
    safer['rank'] = safer.groupby('day', as_index=False)['time'].rank()
    safer['level'] = highest + (3 - safer['rank']) * steps
    return alt.Chart(safer).mark_text(
        clip=True,
        align="center",
        color=colour_best,
        fontSize=16,
    ).encode(
        x="noon:T",
        # Leave space above safe periods for hints (below).
        y=alt.Y("level:Q", scale=alt.Scale(domainMax=highest * 1.4)),
        text="period:N",
        tooltip=["day", "period"],
    )


def hints(sun, label):
    """
    Label above safer periods.
    """
    return alt.Chart(sun).mark_text(
        clip=True,
        tooltip=False,
        align="center",
        baseline="middle",
        color=colour_best,
        fontSize=12,
        dy=20,
    ).encode(
        x="noon:T",
        y=alt.value(0),
        text=alt.value(label),
    )


def crosses(high):
    """
    Red crosses under the high tides.
    """
    return alt.Chart(high).mark_text(
        clip=True,
        tooltip=False,
        align="center",
        color=colour_worst,
        dy=20,
        fontSize=18,
    ).encode(
        x="time:T",
        y="height:Q",
        text=alt.value("✕"),
    )


def icons(sun):
    # FIXME How to position image to avoid clash with chart elements?
    return alt.Chart(sun[1:-1]).mark_image(
        tooltip=False,
        clip=True,
        aspect=True,
        align="center",
        width=50,
    ).encode(
        x="noon:T",
        y=alt.value(-200),
        url=alt.value("/app/static/beach4wd.png"),
    )
