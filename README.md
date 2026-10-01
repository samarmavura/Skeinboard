# LogiMatrices - Supply Chain Analysis Dashboard

This project is a Streamlit-based web application designed to provide insights into supply chain data. It offers a dashboard to analyze various aspects of the supply chain, including inventory, suppliers, and deliveries.

## Features

The application is structured into several modules:

*   **Home**: The main landing page of the application.
*   **Inventory**: Intended for managing and analyzing inventory data. (Under development)
*   **Suppliers**: A comprehensive dashboard for evaluating and analyzing supplier data. This is the most developed feature in the application. It allows you to:
    *   Upload your own supplier data in CSV format or use sample data.
    *   Clean and process the data.
    *   View key performance indicators (KPIs) such as average lead time, defect rate, and total production volume.
    *   Analyze data with interactive charts, including lead time by supplier, defect rate by supplier, and a cost vs. quality scatter plot.
    *   Gain insights into which suppliers are performing above or below average.
*   **Deliveries**: Intended for tracking and analyzing delivery data. (Under development)
*   **Reports**: Intended for generating and viewing reports. (Under development)

## How to Run the Application

1.  **Prerequisites**:
    *   Python 3.7+
    *   pip

2.  **Clone the repository and install the dependencies**:
    ```bash
    git clone <repository-url>
    cd <repository-folder>
    pip install -r requirements.txt
    ```

3.  **Run the Streamlit application**:
    The main application is defined in `app.py`. To run it, execute the following command in your terminal:
    ```bash
    streamlit run app.py
    ```
    This will start the application and open it in your web browser.

## Project Structure

The project is organized as follows:

```
.
├── .venv/                  # Virtual environment
├── app.py                  # Main Streamlit application file
├── delievaries.py          # (Under development) A separate app for deliveries
├── inventory.py            # (Under development) Module for inventory analysis
├── logimatices_logo.png    # Logo image
├── reportings.py           # (Under development) A separate app for reporting
├── reports.py              # (Under development) Module for reports
├── retail_store_inventory.csv # Sample data
├── suppliers.py            # Streamlit page for supplier analysis
├── supply_chain_data.csv   # Sample data
└── requirements.txt        # Python dependencies
```

**Note**: The project contains several files that are currently under development or appear to be experiments (`delievaries.py`, `reportings.py`, `inventory.py`, `reports.py`). The main, functional part of the application is the "Suppliers" page, which is launched from `app.py`.
