"""
A Streamlit.io dashboard for insights into data from various BIEPA projects.
"""
import streamlit as st

st.image("static/tread-lightly.jpg", link="https://biepa.online")
left, right = st.columns(2)
with left:
    st.image("static/tread-lightly-app.jpg", width=400)
with right:
    st.title("We have moved!")
    st.markdown(
        "BIEPA's **Tread Lightly** web app has moved to a new address."
        " To continue using the app to protect nature on Bribie's beaches,"
        " bookmark this link&hellip;"
    )
    st.subheader("[www.treadlightlybribie.app](http://www.treadlightlybribie.app/)", anchor=False)
    st.markdown(
        "You can also reach the new app from the BIEPA website:"
        " [www.biepa.online/tread-lightly](https://biepa.online/tread-lightly)"
    )
st.caption("&copy; Bribie Island Environmental Protection Association Inc.")
# with st.container(horizontal=True, horizontal_alignment="center"):
#     st.image("static/biepa_logo_fullcolour_landscape.png")
