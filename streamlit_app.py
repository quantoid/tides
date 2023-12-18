"""
The safest times are {margin} hours either side of low tide and between dawn and dusk
when there is less danger to wildlife, especially the
[critically endangered loggerhead turtle](https://www.biepa.online/post/critically-endangered-next-stop-extinction)
mothers and hatchlings who nest and hatch on the beach from November to March.
Take all your litter and food home with you; food scraps attract native and feral animals
that prey on turtle eggs and hatchlings.

*Tide data obtained from the [BOM](http://bom.gov.au)
via [Willy Weather](https://www.willyweather.com.au/info/api.html),
interpolation formula thanks to
[Toitū Te Whenua](https://www.linz.govt.nz/products-services/tides-and-tidal-streams/tide-predictions),
concept and design by [Darren Jew](https://darrenjew.com).*

*More [news](https://biepa.online/blog) and [events](https://biepa.online/events)
on the [BIEPA website](https://biepa.online).*

&copy; 2023, Bribie Island Environmental Protection Association Inc.
"""
from types import SimpleNamespace
import streamlit as st
import altair as alt
import pandas as pd

import tide_times

locations = {
    17924: "Ocean Beach, North Bribie Island",
    6781: "Beach Access, Woorim",
}

look_ahead = 5
safe_hours = 3

time_zone = "Australia/Brisbane"
time_format = "%I:%M %p on %a %d %b"

# Colours used on chart.
colour_night = "#d1d3ea"  # lavender
colour_best = "#30a639"  # green
colour_worst = "#c0141b"  # red
colour_water = "#bcdaf2"  # blue
colour_days = "#767676"  # grey


def main():
    settings = show_settings()
    st.image("static/tread-lightly.png", use_column_width="always")
    # Get forecast two days either side of driving date.
    forecast = tide_times.safe_periods(
        where=settings.where,
        when=settings.when - pd.Timedelta(days=2),
        days=look_ahead,
        margin=safe_hours,
    )
    show_chart(forecast)
    st.image("static/checklist.png", use_column_width="always")
    show_table(forecast)
    # show_todo()
    # Use docstring at top of this module for credits etc.
    st.markdown(__doc__.format(margin=safe_hours))


def show_settings():
    with st.sidebar:
        st.image("static/biepa_logo_fullcolour_biepaonly.png")
        st.info(
            "Find the turtle-friendly times to drive on the beach."
            " Be turtle-aware!"
        )
        # Dashboard settings.
        settings = SimpleNamespace()
        choose_where(settings)
        choose_when(settings)
    return settings


def choose_where(settings):
    settings.where = st.selectbox(
        key="location",
        help="The chart will show tide heights for the closest monitoring station.",
        label="Where will you be driving?",
        options=locations,
        index=0,  # Default to first location.
        format_func=locations.get,
    )


def choose_when(settings):
    today = pd.Timestamp.utcnow().tz_convert(time_zone).date()
    saturday = today + pd.Timedelta(days=(5 - today.weekday()) % 7)
    settings.when = st.date_input(
        key="start",
        help="The chart will show tides for three days around this date.",
        label="When will you be driving?",
        value=saturday,
        format="YYYY-MM-DD",
    )


def show_chart(forecast):
    sun = forecast['sun']
    tides = forecast['tides']
    if tides is None:
        st.error("No tide data available for selected location")
        return
    # Get just the times of low and high tides.
    low = tides[tides["type"] == "low"].copy()
    high = tides[tides["type"] == "high"].copy()
    # Create layered chart of tide heights and safer times.
    chart = alt.layer(
        darkness(sun),
        days(sun),
        heights(tides),
        safe(tides, True),
        safe(tides, False),
        crosses(high),
        periods(low, high),
        hints(high),
        # icons(high),  # not working well
    )
    st.altair_chart(
        chart.configure_view(
            stroke="#aaa",
            strokeWidth=1,
            continuousHeight=400,
        ),
        use_container_width=True,
    )


def show_table(forecast):
    # Show location for tide times.
    location = forecast['location']
    maps = (
        "https://www.google.com/maps/@?api=1&map_action=map&zoom=14&basemap=terrain"
        f"&center={location['lat']}%2C{location['lng']}"
    )
    st.markdown(
        "---\nTurtle-friendly driving times for the beach near"
        f" [{location['name']}, {location['region']}, {location['state']}]({maps})"
        f" where times are in {location['timeZone']} time-zone."
    )
    # Show safe periods in a table for small screens.
    tides = forecast['tides']
    if tides is None:
        st.error("No tide data available for selected location")
    else:
        # Exclude times outside chart time window.
        earliest = tides['day'].min() + pd.Timedelta(days=1)
        latest = tides['day'].max() - pd.Timedelta(days=1)
        tides = tides[(tides['day'] >= earliest) & (tides['day'] <= latest)]
        # Get start and end of safer times around low tide.
        tides = tides[(tides['type'] == "low") & tides['earliest'].notnull() & tides['latest'].notnull()]
        st.dataframe(
            data=tides[['day', 'earliest', 'latest']],
            hide_index=True,
            column_config={
                'day': st.column_config.DateColumn(label="Day", width="medium", format="ddd D MMM YYYY"),
                'earliest': st.column_config.DatetimeColumn(label="From", width="medium", format="h:mm a"),
                'latest': st.column_config.DatetimeColumn(label="To", width="medium", format="h:mm a"),
            },
        )


def show_todo():
    # Our to do list.
    st.warning(
        "Planned improvements:\n"
        "\n- Add [focus line on hover](https://altair-viz.github.io/gallery/multiline_tooltip.html)"
        "\n- Add green car icons at low tide."
    )


def darkness(sun):
    """
    Chart of dark periods between daylight periods.
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
    Show label for each day at noon.
    """
    daily = sun.copy()
    # Position labels at midday.
    daily['date'] = daily['dawn'].map(lambda t: t.replace(hour=12, minute=0, second=0))
    # Exclude days outside span of chart.
    daily = daily[(daily['date'] > sun['dusk'].min()) & (daily['date'] < sun['dawn'].max())]
    return alt.Chart(daily).mark_text(
        color=colour_days,
        dy=-12,
        fontSize=16,
    ).encode(
        x="date:T",
        y=alt.value(0),
        text=alt.Text("date:T", format="%a %d %b"),
    )


def heights(tides):
    """
    Area chart of tide heights.
    """
    return alt.Chart(tides).mark_area(
        clip=True,
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
        ),
        tooltip=[
            alt.Tooltip("time", format=time_format),
            alt.Tooltip("height", format=".1f"),
        ],
    )


def safe(tides, okay):
    """
    Line chart of tide height coloured by safety.
    """
    # Hide parts of line that are safe/unsafe.
    line = tides[['time', 'height', 'safe']].copy()
    hide = ~line['safe'] if okay else line['safe']
    line.loc[hide, 'height'] = None
    # Show coloured parts of line that are not hidden.
    return alt.Chart(line).mark_line(
        clip=True,
        color=colour_best if okay else colour_worst,
    ).encode(
        x="time:T",
        y="height:Q",
        tooltip=[
            alt.Tooltip("time", format=time_format),
            alt.Tooltip("height", format=".1f"),
        ],
    )


def periods(low, high):
    time_only = "%I:%M%p"
    safer = low[low['earliest'].notnull() & low['latest'].notnull()].copy()
    safer['period'] = (
        "✓ " + safer['earliest'].dt.strftime(time_only).str.lstrip('0')
        + " - " + safer['latest'].dt.strftime(time_only).str.lstrip('0')
    ).str.lower()
    # Find maximum height to show times above that
    # using steps to get positions of text labels.
    highest = high['height'].max()
    steps = highest * 40 / 400
    # Rank tides by time of day and post labels with the earliest above the latest.
    safer['rank'] = safer.groupby('day', as_index=False)['time'].rank()
    safer['post'] = highest + (4 - safer['rank']) * steps
    return alt.Chart(safer).mark_text(
        clip=True,
        align="center",
        color=colour_best,
        dy=12,
        fontSize=16,
    ).encode(
        x="noon:T",
        y="post:Q",
        text="period:N",
        tooltip=["day", "period"],
    )


def hints(high):
    hint = high.groupby('day', as_index=False).first()
    hint['level'] = high['height'].max() + 0.8
    return alt.Chart(hint).mark_text(
        clip=True,
        tooltip=False,
        align="center",
        color=colour_best,
        dy=12,
        fontSize=12,
    ).encode(
        x="noon:T",
        y="level:Q",
        text=alt.value("travel between"),
    )


def crosses(high):
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


def icons(high):
    noon = high.groupby('day').first()
    # FIXME Image is not shown at this height on chart.
    noon['top'] = high['height'].max() * 1.4
    return alt.Chart(noon).mark_image(
        tooltip=False,
        clip=True,
        aspect=True,
        align="right",
        width=50,
    ).encode(
        x="dusk:T",
        y="top:Q",
        url=alt.value("/app/static/beach4wd.png"),
    )


if __name__ == "__main__":
    # Set up
    st.set_page_config(
        page_title="Tread Lightly on Bribie Island",
        page_icon="🛞",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={
            "About": "Helping visitors to Bribie Island protect endangered wildlife.",
            "Get help": "https://biepa.online/contact",
            "Report a bug": "https://github.com/quantoid/tides/issues",
        }
    )
    main()
