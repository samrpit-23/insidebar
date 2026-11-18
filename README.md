# NSE Inside Bar at Bottom Screener

Finds stocks that fell 10%+ in the last N weeks and are forming an inside bar near the low.
Pick any Nifty segment (50 / 100 / 200 / 500 / Midcap / Smallcap / sectors) from the dropdown.

## Run locally
pip install -r requirements.txt
streamlit run app.py

## Deploy (free) on Streamlit Community Cloud
1. Push this folder to a GitHub repo (app.py at the repo root).
2. Go to https://share.streamlit.io -> New app -> select repo, branch, main file `app.py`.
3. Deploy.

## If NSE blocks the constituent download from the cloud
Download the CSV (e.g. ind_nifty500list.csv) from niftyindices.com and commit it in `data/`.
The app falls back to that folder automatically.
