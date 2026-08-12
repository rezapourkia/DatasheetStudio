import sys

import pymupdf
import PySide6
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel

print("Python:", sys.version)
print("PySide6:", PySide6.__version__)
print("PyMuPDF:", pymupdf.VersionBind)

app = QApplication(sys.argv)

label = QLabel(
    "Datasheet Studio\n\n"
    "PySide6 and PyMuPDF are working correctly."
)
label.setWindowTitle("Environment Test")
label.resize(460, 180)
label.setStyleSheet("""
QLabel {
    background-color: #172033;
    color: #f1f5f9;
    font-size: 18px;
    padding: 30px;
}
""")
label.show()

QTimer.singleShot(5000, app.quit)

exit_code = app.exec()
print("GUI test completed successfully.")
sys.exit(exit_code)
