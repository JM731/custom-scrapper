from PyQt6.QtWidgets import (QApplication,
                             QMainWindow,
                             QPushButton,
                             QWidget,
                             QGridLayout,
                             QHBoxLayout,
                             QLabel,
                             QComboBox,
                             QLineEdit,
                             QTableWidget,
                             QTableWidgetItem,
                             QCheckBox,
                             QAbstractItemView,
                             QFileDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import bs4.element
from bs4 import BeautifulSoup
import requests
from requests.exceptions import ConnectionError
import pandas as pd

# TODO handle connectivity exceptions

NO_CONNECTION = "Could not connect to source. Please try again."
us_url = "https://psdeals.net/us-store"
search_url_list = ["https://psdeals.net/", "-store/search"]


def value_selector(game: bs4.element.Tag, class_: str, alt_class=None):
    property_ = game.select_one(class_)
    if property_:
        return property_.text
    else:
        if alt_class:
            property_ = game.select_one(alt_class)
            if property_:
                return property_.text
        return '0'


def get_regions():
    region_response = requests.get(url=us_url)
    region_soup = BeautifulSoup(region_response.text, 'html.parser')
    regions = [region.text for region in region_soup.select("#dropdown-region-menu span")]
    acronyms = {region: region.split(" |")[0][-2:].lower() for region in regions}
    return acronyms


def search_games(search_url: str, params: dict):
    search_response = requests.get(search_url, params=params)
    search_soup = BeautifulSoup(search_response.text, 'html.parser')
    game_list = search_soup.select(".game-collection-item")
    names_list = [game.select_one(".game-collection-item-details-title").text for game in game_list]
    link_list = [game.find("a").get("href") for game in game_list]
    discounts_list = [value_selector(game, ".game-collection-item-discount") for game in game_list]
    prices_list = [value_selector(game,
                                  ".game-collection-item-price",
                                  alt_class=".game-collection-item-price.strikethrough") for game in game_list]
    discounted_prices_list = [value_selector(game,
                                             ".game-collection-item-price-discount",
                                             alt_class=".game-collection-item-price") for game in game_list]

    current_data = {
        'Game': names_list,
        'Price': prices_list,
        'Discount': discounts_list,
        'Discounted Price': discounted_prices_list,
        'Link': link_list
    }
    return current_data


def search_lowest_price(selected_link):
    search_response = requests.get(selected_link)
    search_soup = BeautifulSoup(search_response.text, 'html.parser')
    lowest_price = search_soup.select_one(".game-stats-col-number-big.game-stats-col-number-green").text
    return lowest_price


class Window(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlayStation Price Search")
        self.setMinimumSize(850, 500)
        self.regions = None
        self.search_query = None
        self.game_data = pd.DataFrame(columns=["Game", "Price", "Discount", "Discounted Price"])
        self.displayed_data = pd.DataFrame(columns=["Game", "Price", "Discount", "Discounted Price", "Link"])
        self.current_data = None
        self.selected_title = None

        self.region_combobox = QComboBox()
        self.region_combobox.setMaxVisibleItems(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for a title...")
        self.search_button = QPushButton("Search")
        self.search_button.setDisabled(True)
        self.to_data_button = QPushButton("Add to CSV data")
        self.to_data_button.setDisabled(True)
        self.generate_csv = QPushButton("Generate CSV file")
        self.generate_csv.setDisabled(True)
        self.retry_button = QPushButton("Retry connecting")
        self.retry_button.hide()
        self.clear_checkbox = QCheckBox("Clear table on search")
        self.lowest_price_button = QPushButton("Lowest price")
        self.lowest_price_button.setDisabled(True)
        self.lowest_price_label = QLabel("Select an item")
        status_font = QFont()
        status_font.setPointSize(16)
        self.status_label = QLabel("")
        self.status_label.setFont(status_font)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Game", "Price", "Discount", "Discounted Price", "Link"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 350)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        self.search_button.clicked.connect(self.search)
        self.to_data_button.clicked.connect(self.addToData)
        self.generate_csv.clicked.connect(self.generateCSV)
        self.lowest_price_button.clicked.connect(self.searchLowestPrice)
        self.retry_button.clicked.connect(self.getRegions)
        self.search_input.textEdited.connect(self.onTextChanged)
        self.table.itemSelectionChanged.connect(self.handleSelectionChanged)

        self.getRegions()
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        layout = QGridLayout()
        file_layout = QHBoxLayout()

        file_layout.addWidget(self.to_data_button)
        file_layout.addWidget(self.generate_csv)
        layout.addWidget(self.status_label, 0, 0, 1, 5)
        layout.addWidget(self.retry_button, 1, 2, 1, 1)
        layout.addWidget(self.table, 2, 0, 4, 5)
        layout.addWidget(self.search_input, 6, 0, 1, 3)
        layout.addWidget(self.region_combobox, 6, 3, 1, 1)
        layout.addWidget(self.search_button, 6, 4, 1, 1)
        layout.addWidget(self.lowest_price_button, 7, 0, 1, 1)
        layout.addWidget(self.lowest_price_label, 7, 1, 1, 3)
        layout.addWidget(self.clear_checkbox, 7, 4, 1, 1)
        layout.addLayout(file_layout, 8, 1, 1, 3)

        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

        self.show()

    def getRegions(self):
        try:
            self.regions = get_regions()
        except ConnectionError:
            if self.retry_button.isHidden():
                self.retry_button.show()
                self.status_label.show()
                self.status_label.setText(NO_CONNECTION)
            else:
                self.retry_button.setDisabled(True)
                QTimer.singleShot(500, lambda: self.retry_button.setDisabled(False))
        else:
            if not self.retry_button.isHidden():
                self.retry_button.hide()
                self.status_label.setText("Connection established.")
            for key in self.regions:
                self.region_combobox.addItem(key)

    def search(self):
        if self.status_label.isHidden():
            self.status_label.show()
        self.search_query = self.search_input.text()
        self.search_button.setDisabled(True)
        search_url = search_url_list[0] + self.regions[self.region_combobox.currentText()] + search_url_list[1]
        params = {"search_query": self.search_query}

        try:
            self.current_data = search_games(search_url, params)

        except ConnectionError:
            self.status_label.setText(NO_CONNECTION)
            self.search_query = None
            QTimer.singleShot(400, lambda: self.search_button.setDisabled(False))
        else:
            if self.current_data["Game"]:

                if self.clear_checkbox.isChecked():
                    self.table.clearContents()
                    self.table.setRowCount(0)
                    self.displayed_data = pd.DataFrame(columns=["Game",
                                                                "Price",
                                                                "Discount",
                                                                "Discounted Price",
                                                                "Link"])

                row = self.table.rowCount()
                data_len = len(self.current_data["Game"])

                self.status_label.setText(f"Found {data_len} games!")

                self.table.setRowCount(row + data_len)
                for i in range(data_len):
                    self.table.setItem(row, 0, QTableWidgetItem(self.current_data["Game"][i]))
                    self.table.setItem(row, 1, QTableWidgetItem(self.current_data["Price"][i]))
                    self.table.setItem(row, 2, QTableWidgetItem(self.current_data["Discount"][i]))
                    self.table.setItem(row, 3, QTableWidgetItem(self.current_data["Discounted Price"][i]))
                    row += 1

                self.displayed_data = pd.concat([self.displayed_data, pd.DataFrame(self.current_data)],
                                                ignore_index=True)
                self.to_data_button.setDisabled(False)

            else:

                self.status_label.setText("No games were found!")

    def onTextChanged(self):
        text = self.search_input.text()
        if not text or text == self.search_query:
            self.search_button.setDisabled(True)
        else:
            self.search_button.setDisabled(False)

    def searchLowestPrice(self):
        row = self.table.selectionModel().currentIndex().row()
        title = self.displayed_data["Game"].loc[row]
        if title != self.selected_title:
            selected_link = search_url_list[0][:-1] + self.displayed_data['Link'].loc[row]
            try:
                lowest_price = search_lowest_price(selected_link)
            except ConnectionError:
                self.status_label.setText(NO_CONNECTION)
                self.lowest_price_button.setDisabled(True)
                QTimer.singleShot(500, lambda: self.lowest_price_button.setDisabled(False))
            else:
                self.selected_title = title
                self.lowest_price_label.setText(f"{self.selected_title}: {lowest_price}")

    def addToData(self):
        self.game_data = pd.concat([self.game_data,
                                    self.displayed_data[["Game", "Price", "Discount", "Discounted Price"]]],
                                   ignore_index=True)
        self.to_data_button.setDisabled(True)
        self.generate_csv.setDisabled(False)
        self.status_label.setText("The current games were added to CSV data.")

    def generateCSV(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "",
                                                   "CSV (*.csv)")
        if file_path:
            self.game_data.to_csv(file_path, index=False)
            self.status_label.setText("CSV file created!")

    def handleSelectionChanged(self):
        selected_rows = self.table.selectedItems()
        if len(selected_rows) == 4:
            if not self.lowest_price_button.isEnabled():
                self.lowest_price_button.setDisabled(False)
        else:
            self.lowest_price_button.setDisabled(True)


if __name__ == "__main__":
    main_event_thread = QApplication([])
    main_event_thread.setQuitOnLastWindowClosed(True)
    window = Window()
    main_event_thread.exec()
