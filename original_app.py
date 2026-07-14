"""
The safest times are {margin} hours either side of low tide and between dawn and dusk
when there is less danger to wildlife, especially the
[critically endangered loggerhead turtle](https://www.biepa.online/post/critically-endangered-next-stop-extinction)
mothers and hatchlings who nest and hatch on the beach from November to March.
Take all your litter and food home with you; food scraps attract native and feral animals
that prey on turtle eggs and hatchlings.

Please send helpful feedback to the BIEPA Wildlife Team at: wildlife@biepa.online

*Tide data obtained from the [BOM](http://bom.gov.au)
via [Willy Weather](https://www.willyweather.com.au/info/api.html),
interpolation formula thanks to
[Toitū Te Whenua](https://www.linz.govt.nz/products-services/tides-and-tidal-streams/tide-predictions),
coding by Mike Howells,
concept and design by [Darren Jew](https://darrenjew.com).*

*More [news](https://biepa.online/blog) and [events](https://biepa.online/events)
on the [BIEPA website](https://biepa.online).*
"""
from types import SimpleNamespace
import streamlit as st
import altair as alt
import pandas as pd

import tide_times
import chart_layers

locations = {
    6781: "Southern Access Track, Woorim Beach",
    17924: "Northern Access Track, Ocean Beach",
}

days_shown = 5
safe_hours = 3


def main():
    with st.sidebar:
        show_sidebar()
    # Main area with placeholders for tides and times.
    st.image("static/tread-lightly.jpg", use_container_width=True)
    tides = st.container()
    st.image("static/checklist.jpg", use_container_width=True)
    st.success("🔄 &nbsp; If using your phone, rotate to landscape mode for a better view of the chart.")
    settings = show_settings()
    times = st.container()
    # Get forecast equal days either side of driving date and show tides and times.
    forecast = tide_times.safe_periods(
        where=settings.where,
        when=settings.when - pd.Timedelta(days=int(days_shown / 2)),
        days=days_shown,
        margin=safe_hours,
    )
    with tides:
        show_chart(forecast)
    with times:
        show_table(forecast)
    # Use docstring at top of this module for credits etc.
    st.markdown(__doc__.format(margin=safe_hours))


def show_sidebar():
    st.image("static/biepa_logo_fullcolour_biepaonly.png")
    st.info(
        "Find the turtle-friendly times to drive on the beach."
        " Be turtle-aware!"
    )
    st.markdown(
        "<small>&copy; 2023, Bribie Island Environmental Protection Association Inc.</small>",
        unsafe_allow_html=True,
    )


def show_settings():
    settings = SimpleNamespace()
    left, right = st.columns(2)
    with left:
        settings.when = st.date_input(
            key="when",
            help="The chart will show tides for three days around this date.",
            label="When will you be driving?",
            value=url_value(key="when", convert=to_date, default="today"),
            format="YYYY-MM-DD",
        )
    with right:
        settings.where = st.selectbox(
            key="where",
            help="The chart will show tide heights for the closest monitoring station.",
            label="Where will you be driving?",
            options=locations,
            index=0,  # Default to first location.
            format_func=locations.get,
        )
    return settings


def url_value(key, convert=None, default=None):
    value = st.session_state.get(key)
    if value is not None:
        return value
    value = st.query_params.get(key)
    if value is not None:
        return convert(value[0]) if convert else value[0]
    return default


def to_date(string):
    return pd.Timestamp(string).date()


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
    # NOTE: Order is important as layers overlap.
    chart = alt.layer(
        chart_layers.darkness(sun),
        chart_layers.days(sun),
        chart_layers.heights(tides),
        chart_layers.curve(tides, safe=True),
        chart_layers.curve(tides, safe=False),
        chart_layers.crosses(high),
        chart_layers.periods(low, high),
        chart_layers.hints(high, label="travel between"),
        # chart_layers.icons(high),  # not working yet
    )
    st.altair_chart(
        chart.configure_view(
            stroke="#aaa",
            strokeWidth=1,
            continuousHeight=400,
        ).properties(
            width='container',
        ).interactive(bind_y=False),
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
        "Turtle-friendly driving times for the beach near"
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


if __name__ == "__main__":
    # Streamlit preferences.
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
