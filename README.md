# ITC & GST Reconciliation App

An automated Python and Streamlit application designed to perform Input Tax Credit (ITC) reconciliation between internal purchase books and GSTR-2B data, equipped with machine-learning vendor risk assessment and automated report generation.

## Features

* **ITC Matching Engine**: Automatically reconciles financial records against GSTR-2B tax data.
* **Vendor Risk Profiling**: Uses ML logic (`vendor_risk.py`) to flag non-compliant or high-risk vendors.
* **Report Generation**: Exports detailed reconciliation reports in Excel and PDF formats.
* **Database Integration**: Manages historical reconciliation data automatically using SQLite.

## Project Structure
