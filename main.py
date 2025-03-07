import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import ctypes
import numpy as np

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QMessageBox, \
    QScrollArea
from PyQt6.QtGui import QIcon, QPixmap, QCursor
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


# Function to load data from a CSV file
def load_data(filename):
    try:
        data = pd.read_csv(filename)  # Load the CSV file into a DataFrame
        return data
    except FileNotFoundError:  # Handle the case where the file is not found
        QMessageBox.critical(None, "Error", "File not found. Please check the file path and try again.")
        return None


# Function to create necessary tables in the SQLite database
def create_tables(db_name='hotel_bookings.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS average_nights (
        hotel TEXT PRIMARY KEY,
        average_nights REAL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cancellation_rate (
        hotel TEXT PRIMARY KEY,
        cancellation_rate REAL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS booking_categories (
        category TEXT PRIMARY KEY,
        count INTEGER
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS booking_distribution (
        arrival_date_month TEXT,
        hotel TEXT,
        count INTEGER,
        PRIMARY KEY (arrival_date_month, hotel)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS room_type_distribution (
        reserved_room_type TEXT PRIMARY KEY,
        count INTEGER
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS category_distribution (
        category TEXT PRIMARY KEY,
        count INTEGER
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS booking_trends (
        date TEXT PRIMARY KEY,
        count INTEGER
    )
    ''')

    conn.commit()
    conn.close()


# Function to calculate statistics from the data
def calculate_statistics(data):
    if data is not None:
        # Calculate total nights stayed by summing weekend and week nights
        data['total_nights'] = data['stays_in_weekend_nights'] + data['stays_in_week_nights']
        # Calculate average nights stayed per hotel
        avg_nights = data.groupby('hotel')['total_nights'].mean()
        # Calculate cancellation rate per hotel
        cancellation_rate = data.groupby('hotel')['is_canceled'].mean()
        return avg_nights, cancellation_rate
    else:
        return None, None


# Function to create a plot for booking distribution by month
def create_plot(data):
    plt.figure(figsize=(10, 6))
    ax = sns.countplot(x='arrival_date_month', hue='hotel', data=data, palette='coolwarm')
    # Annotate each bar with its height
    for bar in ax.patches:
        ax.annotate(format(bar.get_height(), '.2f'),
                    (bar.get_x() + bar.get_width() / 2,
                     bar.get_height()), ha='center', va='center',
                    size=9, xytext=(0, 5),
                    textcoords='offset points')

    plt.title('Booking Distribution by Month')
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Extract data used in the plot
    plot_data = data.groupby(['arrival_date_month', 'hotel']).size().reset_index(name='count')

    return plt.gcf(), ax, plot_data  # Returns the current matplotlib figure, axis, and plot data


# Function to plot room type distribution
def plot_room_type_distribution(data):
    plt.figure(figsize=(10, 6))
    ax = sns.countplot(x='reserved_room_type', data=data)
    # Generate a color palette and set colors for each bar
    palette = sns.color_palette("magma", len(data['reserved_room_type'].unique()))
    for bar, color in zip(ax.patches, palette):
        bar.set_facecolor(color)

    for bar in ax.patches:
        ax.annotate(format(bar.get_height(), '.2f'),
                    (bar.get_x() + bar.get_width() / 2,
                     bar.get_height()), ha='center', va='center',
                    size=9, xytext=(0, 5),
                    textcoords='offset points')

    plt.title('Distribution of Bookings by Room Type')
    plt.xlabel('Room Type')
    plt.ylabel('Number of Bookings')
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Extract data used in the plot
    plot_data = data['reserved_room_type'].value_counts().reset_index()
    plot_data.columns = ['reserved_room_type', 'count']

    return plt.gcf(), ax, plot_data  # Return the figure, axis, and plot data


# Function to categorize bookings based on the number of adults, children, and babies
def categorize_bookings(data):
    # Define conditions for categorizing bookings
    conditions = [
        (data['adults'] == 1) & (data['children'] == 0) & (data['babies'] == 0),
        (data['adults'] == 2) & (data['children'] == 0) & (data['babies'] == 0),
        (data['adults'] > 2) | (data['children'] > 0) | (data['babies'] > 0)
    ]
    choices = ['Individual', 'Couple', 'Family']
    data['category'] = pd.Categorical(np.select(conditions, choices, default='Other'))
    category_counts = data['category'].value_counts().reset_index()
    category_counts.columns = ['category', 'count']
    return category_counts  # Return the counts of each category as a DataFrame


# Funciont o plot booking trends over time
def plot_booking_trends(data):
    plt.figure(figsize=(12, 6))
    # Convert 'arrival_date_year' and 'arrival_date_month' to a datetime object.
    # Specifying the format to avoid the UserWarning and ensure efficient parsing.
    # The format '%Y-%B' stands for four-digit year and full month name.
    # The general overview is that I convert the 'arrival_date_year' and
    # 'arrival_date_month' to a datetime object.
    data['date'] = pd.to_datetime(data['arrival_date_year'].astype(str) + '-' + data['arrival_date_month'],
                                  format='%Y-%B')

    # Aggregate data by new 'date' column
    monthly_data = data.groupby('date').size().reset_index(name='count')
    ax = monthly_data.plot(kind='line', marker='o', color='tab:blue', title='Monthly Booking Trends')
    ax.set_xlabel('Month')
    ax.set_ylabel('Number of Bookings')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    return plt.gcf(), ax, monthly_data  # Return the figure, axis, and plot data


# Function to plot seasonality trends
def plot_seasonality(data):
    month_order = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    plt.figure(figsize=(16, 8))

    colors = {
        ('Resort Hotel', 'total_bookings'): 'blue',
        ('Resort Hotel', 'is_canceled'): 'lightblue',
        ('City Hotel', 'total_bookings'): 'green',
        ('City Hotel', 'is_canceled'): 'lightgreen'
    }

    data['month_key'] = pd.Categorical(data['arrival_date_month'], categories=month_order, ordered=True)
    grouped = data.groupby(['hotel', 'month_key'], observed=True).agg({
        'is_canceled': 'sum',  # Count of cancellations
        'reservation_status_date': 'count'  # Count of all bookings
    }).rename(columns={'reservation_status_date': 'total_bookings'}).unstack(0).fillna(0)

    width = 0.2  # the width of the bars
    fig, ax = plt.subplots()
    positions = np.arange(len(month_order))  # positions for the groups

    # Plot bars for each category and hotel
    for i, ((hotel, metric), color) in enumerate(colors.items()):
        offsets = {'City Hotel': -width / 2, 'Resort Hotel': width / 2}
        bar_positions = positions + offsets[hotel]
        ax.bar(bar_positions, grouped[metric][hotel], width, label=f"{hotel} {metric}", color=color, align='edge')

    ax.set_xlabel('Month')
    ax.set_ylabel('Count')
    ax.set_title('Booking Trends by Hotel Type and Status')
    ax.set_xticks(positions)
    ax.set_xticklabels(month_order)
    plt.xticks(rotation=45)
    plt.legend()

    # Annotate each bar with its height
    for rect in ax.patches:
        height = rect.get_height()
        if height > 0:  # Only annotate if height is greater than zero to avoid clutter
            ax.annotate(f'{int(height)}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    plt.tight_layout()
    return plt.gcf()


# Function to save DataFrame to SQLite table
def save_to_sqlite(data, table_name, db_name='hotel_bookings.db'):
    conn = sqlite3.connect(db_name)
    data.to_sql(table_name, conn, if_exists='replace', index=False)
    conn.close()


# Function to export SQLite table to CSV
def export_to_csv(table_name, db_name='hotel_bookings.db'):
    conn = sqlite3.connect(db_name)
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    df.to_csv(f"{table_name}.csv", index=False)
    conn.close()


# Function to insert data into SQLite table
def insert_into_table(data, table_name, db_name='hotel_bookings.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for index, row in data.iterrows():
        cursor.execute(f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?)", (row[0], row[1]))
    conn.commit()
    conn.close()


# Function to insert data into SQLite table
def insert_into_table_(data, table_name, db_name='hotel_bookings.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for index, row in data.iterrows():
        cursor.execute(f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?, ?)", tuple(row))
    conn.commit()
    conn.close()


# Function to insert data into SQLite table
def insert_into_table__(data, table_name, db_name='hotel_bookings.db'):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    if table_name == "booking_distribution":
        for index, row in data.iterrows():
            cursor.execute(f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?, ?)", tuple(row))
    elif table_name == "booking_trends":
        for index, row in data.iterrows():
            cursor.execute(f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?)", (str(row[0]), row[1]))
    else:
        for index, row in data.iterrows():
            cursor.execute(f"INSERT OR REPLACE INTO {table_name} VALUES (?, ?)", (row[0], row[1]))
    conn.commit()
    conn.close()



# Class defining the main window of the application
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.canvas = None  # Placeholder for the canvas
        self.scroll_area = None  # Placeholder for the scroll area

        self.setWindowTitle("Hotel Booking Analysis")
        self.UPatras_icon = QIcon("Images/up_2017_logo_en.ico")
        self.setWindowIcon(self.UPatras_icon)
        self.setMinimumSize(800, 600)  # Set the minimum size to prevent resizing below one value

        # Automatically load data
        self.data = load_data('hotel_booking.csv')

        # Create tables in the database
        create_tables()

        # Layout
        self.layout = QVBoxLayout()

        ########### Widgets ##############
        self.UPatras_logo_png = QPixmap("Images/up_2017_logo_en_resized.png")
        self.UPatras_logo = QLabel()
        self.btn_distribution_per_month_epoch = QPushButton("Distribution per month and per epoch")
        self.btn_avg_nights = QPushButton("Average Nights and Cancellation")
        self.btn_room_type_distribution = QPushButton("Distribution by Room Type")
        self.btn_category_distribution = QPushButton("Booking Category Distribution")
        self.btn_booking_trends = QPushButton("Show Booking Trends")
        self.btn_seasonality = QPushButton("Analyze Seasonality")
        self.btn_export = QPushButton("Export Results to CSV")
        self.btn_back = QPushButton("Back")
        self.central_widget = QWidget()

        self.setupUI()

    def setupUI(self):
        # Button Styling
        button_style = """
                QPushButton {
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, 
                                                      stop:0 rgba(105, 181, 255, 255), 
                                                      stop:1 rgba(65, 131, 215, 255));
                    color: white;
                    border-radius: 10px;
                    padding: 10px;
                    font-size: 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                                                      stop:0 rgba(65, 131, 215, 255), 
                                                      stop:1 rgba(25, 81, 165, 255));
                }
                QPushButton:pressed {
                    background-color: rgba(25, 81, 165, 255);
                }
                """

        # Set style
        self.btn_distribution_per_month_epoch.setStyleSheet(button_style)
        self.btn_avg_nights.setStyleSheet(button_style)
        self.btn_back.setStyleSheet(button_style)
        self.btn_room_type_distribution.setStyleSheet(button_style)
        self.btn_category_distribution.setStyleSheet(button_style)
        self.btn_booking_trends.setStyleSheet(button_style)
        self.btn_seasonality.setStyleSheet(button_style)
        self.btn_export.setStyleSheet(button_style)

        # Set Cursor while hover over buttons
        self.btn_distribution_per_month_epoch.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_avg_nights.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_room_type_distribution.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_category_distribution.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_booking_trends.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_seasonality.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Back Button
        self.btn_back.clicked.connect(self.show_initial_ui)
        self.btn_back.hide()  # initially hide the back button
        self.layout.addWidget(self.btn_back, alignment=Qt.AlignmentFlag.AlignLeft)

        self.UPatras_logo.setPixmap(self.UPatras_logo_png)
        self.layout.addWidget(self.UPatras_logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Buttons for different analyses
        self.btn_distribution_per_month_epoch.clicked.connect(self.show_plot)
        self.layout.addWidget(self.btn_distribution_per_month_epoch)
        self.layout.addSpacing(25)

        self.btn_avg_nights.clicked.connect(self.average_nights_and_cancellation)
        self.layout.addWidget(self.btn_avg_nights)
        self.layout.addSpacing(25)

        self.btn_room_type_distribution.clicked.connect(self.show_room_type_distribution)
        self.layout.addWidget(self.btn_room_type_distribution)
        self.layout.addSpacing(25)

        self.btn_category_distribution.clicked.connect(self.show_category_distribution)
        self.layout.addWidget(self.btn_category_distribution)
        self.layout.addSpacing(25)

        self.btn_booking_trends.clicked.connect(self.show_booking_trends)
        self.layout.addWidget(self.btn_booking_trends)
        self.layout.addSpacing(25)

        self.btn_seasonality.clicked.connect(self.show_seasonality)
        self.layout.addWidget(self.btn_seasonality)
        self.layout.addSpacing(25)

        self.btn_export.clicked.connect(self.export_results)
        self.layout.addWidget(self.btn_export)

        # Set the central widget of the Window.
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

    # Function to display average nights and cancellation rates
    def average_nights_and_cancellation(self):
        if self.data is not None:
            avg_nights, cancel_rate = calculate_statistics(self.data)
            avg_nights_df = avg_nights.reset_index().rename(columns={0: 'average_nights'})
            cancel_rate_df = cancel_rate.reset_index().rename(columns={0: 'cancellation_rate'})
            insert_into_table(avg_nights_df, 'average_nights')
            insert_into_table(cancel_rate_df, 'cancellation_rate')
            message = f"Average Nights:\n{avg_nights}\n\nCancellation Rate:\n{cancel_rate}"
            QMessageBox.information(self, "Statistics", message)
        else:
            QMessageBox.warning(self, "Data Not Loaded", "Please check the data file.")

    # Function to show the booking distribution plot
    def show_plot(self):
        fig, ax, plot_data = create_plot(self.data)
        insert_into_table_(plot_data, 'booking_distribution')
        if self.canvas is None:
            self.canvas = FigureCanvas(fig)  # Create the canvas with the figure
            self.scroll_area = FigureCanvas(fig)  # Create a scroll area
            self.scroll_area = QScrollArea()  # Create a Scroll area
            self.scroll_area.setWidget(self.canvas)  # Set the canvas as the widget to scroll
            self.scroll_area.setWidgetResizable(True)  # Allow the canvas to resize with the scroll area
            self.layout.addWidget(self.scroll_area)
        else:
            self.canvas.figure = fig  # Update the figure
            self.canvas.draw()

        self.hide_buttons()
        self.btn_back.show()

    # Function to show room type distribution plot
    def show_room_type_distribution(self):
        fig, ax, plot_data = plot_room_type_distribution(self.data)
        insert_into_table(plot_data, 'room_type_distribution')  # Save the plot data to the SQLite table
        if self.canvas is None:
            self.canvas = FigureCanvas(fig)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidget(self.canvas)
            self.scroll_area.setWidgetResizable(True)
            self.layout.addWidget(self.scroll_area)
        else:
            self.canvas.figure = fig
            self.canvas.draw()

        self.hide_buttons()
        self.btn_back.show()

    # Function to show booking category distribution
    def show_category_distribution(self):
        category_counts = categorize_bookings(self.data)
        insert_into_table(category_counts, 'booking_categories')
        message = "\n".join([f"{cat}: {count}" for cat, count in category_counts.items()])
        QMessageBox.information(self, "Booking Categories", message)

    # Function to show booking trends plot
    def show_booking_trends(self):
        fig, ax, plot_data = plot_booking_trends(self.data)
        insert_into_table__(plot_data, 'booking_trends')
        if self.canvas is None:
            self.canvas = FigureCanvas(fig)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidget(self.canvas)
            self.scroll_area.setWidgetResizable(True)
            self.layout.addWidget(self.scroll_area)
        else:
            self.canvas.figure = fig
            self.canvas.draw()

        self.hide_buttons()
        self.btn_back.show()

    # Function to show seasonality analysis plot
    def show_seasonality(self):
        fig = plot_seasonality(self.data)
        if self.canvas is None:
            self.canvas = FigureCanvas(fig)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidget(self.canvas)
            self.scroll_area.setWidgetResizable(True)
            self.layout.addWidget(self.scroll_area)
        else:
            self.canvas.figure = fig
            self.canvas.draw()

        self.hide_buttons()
        self.btn_back.show()

    # Function to export results to CSV
    def export_results(self):
        export_to_csv('average_nights')
        export_to_csv('cancellation_rate')
        export_to_csv('booking_categories')
        export_to_csv('booking_distribution')
        export_to_csv('room_type_distribution')
        export_to_csv('category_distribution')
        export_to_csv('booking_trends ')
        QMessageBox.information(self, "Export Complete", "Results have been exported to CSV files.")

    # Function to show initial UI layout
    def show_initial_ui(self):
        if self.canvas:
            self.canvas.hide()
            self.canvas = None
            self.scroll_area.hide()
            self.scroll_area = None

        self.btn_avg_nights.show()
        self.btn_distribution_per_month_epoch.show()
        self.btn_room_type_distribution.show()
        self.btn_category_distribution.show()
        self.btn_booking_trends.show()
        self.btn_seasonality.show()
        self.btn_export.show()
        self.btn_back.hide()

    # Function to hide all buttons
    def hide_buttons(self):
        self.btn_avg_nights.hide()
        self.btn_distribution_per_month_epoch.hide()
        self.btn_room_type_distribution.hide()
        self.btn_category_distribution.hide()
        self.btn_booking_trends.hide()
        self.btn_seasonality.hide()
        self.btn_export.hide()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app_id = 'Arxes_Glosswn'
    #ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
