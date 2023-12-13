"""
Show chart of tide heights with driving times that are safer for turtles.
"""
import streamlit as st
import altair as alt
import pandas as pd
import willy


location_id = 17924
look_ahead = 5
safe_hours = 3
time_format = "%I:%M %p on %a %d %b"

# Colours used on chart.
colour_night = "#d1d3ea"  # lavender
colour_best = "#30a639"  # green
colour_worst = "#c0141b"  # red
colour_water = "#bcdaf2"  # blue
colour_days = "#767676"  # grey


def main():
    with st.sidebar:
        show_settings()
    st.image("static/tread-lightly.png", use_column_width="always")
    forecast = get_forecast(when=pd.Timestamp.now().date())
    show_chart(forecast)
    st.image("static/checklist.png", use_column_width="always")
    show_table(forecast)
    show_todo()


def show_settings():
    st.image("static/biepa_logo_fullcolour_biepaonly.png")
    st.title("Tread Lightly")
    st.markdown("Turtle-friendly times to drive on the beach.")


def get_forecast(when):
    # Get sun and tide data for next weekend.
    thursday = when + pd.Timedelta(days=(3 - when.weekday()) % 7)
    return willy.forecast(where=location_id, when=thursday, days=look_ahead, margin=safe_hours)


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
        hints(low),
        # icons(low),
    )
    st.altair_chart(
        chart.configure_view(stroke="#aaa", strokeWidth=1),
        use_container_width=True,
    )


def show_table(forecast):
    # Show location for tide times.
    location = forecast['where']
    maps = (
        "https://www.google.com/maps/@?api=1&map_action=map&zoom=14&basemap=terrain"
        f"&center={location['lat']}%2C{location['lng']}"
    )
    st.markdown(
        "---\nTurtle-friendly driving times this weekend for beaches near"
        f" [{location['name']}, {location['region']}, {location['state']}]({maps})"
        f" where times are in {location['timeZone']} time-zone."
    )
    # Show safe periods in a table for small screens.
    tides = forecast['tides']
    if tides is None:
        st.error("No tide data available for selected location")
    else:
        st.dataframe(
            data=tides[tides['type'] == "low"][['day', 'earliest', 'latest']],
            hide_index=True,
            column_config={
                'day': st.column_config.DateColumn(label="Day", width="medium", format="ddd D MMM YYYY"),
                'earliest': st.column_config.DatetimeColumn(label="From", width="medium", format="h:mm a"),
                'latest': st.column_config.DatetimeColumn(label="To", width="medium", format="h:mm a"),
            },
        )
    st.markdown(
        f"\n\nThe safest times are {safe_hours} hours either side of low tide and between dawn and dusk"
        " when there is less danger to wildlife, including the"
        " [critically endangered loggerhead turtle]"
        "(https://www.biepa.online/post/critically-endangered-next-stop-extinction)"
        " mothers and hatchlings who nest and hatch on the beach from November to March."
        "\n\n*Tide data from the BOM via [Willy Weather](https://www.willyweather.com.au/info/api.html)*."
        f"\n\n*More [news](https://biepa.online/blog) and [events](https://biepa.online/events) on the BIEPA website.*"
        "\n\n&copy; 2023, Bribie Island Environmental Protection Association Inc."
    )


def show_todo():
    # Our to do list.
    st.warning(
        "Planned improvements:\n"
        "\n- Add [focus line on hover](https://altair-viz.github.io/gallery/multiline_tooltip.html)"
        "\n- Add green car icons at low tide."
        "\n- Select future date in sidebar."
        "\n- Select from predefined locations of 4WD beaches in sidebar."
    )


def select_location():
    search = st.text_input(
        key="search",
        help="Find locations for which we have data on tides.",
        label="Search by postcode or name",
    )
    locations = willy.search(search) if search else []
    location = st.selectbox(
        key="location",
        help="Choose a location to see tide times.",
        label="Select location",
        options=locations,
        disabled=not locations,
        format_func=lambda i: i['name'],
    )
    st.text(f"id = {location['id']}")
    return location


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


def hints(low):
    time = "%I:%M%p"
    low['period'] = (
        "✓ " + low['earliest'].dt.strftime(time).str.lstrip('0')
        + " - " + low['latest'].dt.strftime(time).str.lstrip('0')
    ).str.lower()
    return alt.Chart(low).mark_text(clip=True, color=colour_best, dy=12, fontSize=16).encode(
        x="time:T",
        y="height:Q",
        text="period:N",
        tooltip=["day", "period"],
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


def icons(low):
    low['icon'] = "/app/static/beach4wd.png"
    return alt.Chart(low).mark_image(aspect=True, align="center", dy=40).encode(
        x="time:T",
        y="height:Q",
        url="icon",
        tooltip=[
            alt.Tooltip("time", format=time_format),
            alt.Tooltip("height", format=".1f"),
        ],
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
