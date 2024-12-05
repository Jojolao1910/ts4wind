import sys
import json
import hashlib
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QListWidget, QTabWidget, QLabel, QLineEdit, 
                             QMessageBox, QInputDialog, QSpinBox, QFormLayout, QCheckBox,
                             QComboBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox)
from PyQt6.QtCore import Qt, QTimer
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

class Profile:
    def __init__(self, name):
        self.name = name
        self.macros = {}
        self.button_assignments = {}

class Macro:
    def __init__(self, name):
        self.name = name
        self.actions = []
        self.repeat = False
        self.trigger_on_press = True
        self.delay = 10  # Default delay in milliseconds

class Action:
    def __init__(self, action_type, **kwargs):
        self.type = action_type
        self.button = kwargs.get('button')
        self.x = kwargs.get('x')
        self.y = kwargs.get('y')
        self.scroll_amount = kwargs.get('scroll_amount')
        self.delay = kwargs.get('delay', 0)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login")
        self.username = QLineEdit(self)
        self.password = QLineEdit(self)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Username:"))
        layout.addWidget(self.username)
        layout.addWidget(QLabel("Password:"))
        layout.addWidget(self.password)
        layout.addWidget(self.buttonBox)
        
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

class TS4Windows(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TS4Windows")
        self.setGeometry(100, 100, 800, 600)

        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.profiles = []
        self.current_profile = None
        self.recording = False
        self.current_macro = None
        self.macro_timer = QTimer(self)
        self.macro_timer.timeout.connect(self.execute_macro_step)
        self.current_macro_index = 0

        self.users = {}  # Store user credentials
        self.load_users()

        if not self.show_login():
            sys.exit()

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_profiles_tab(), "Profiles")
        self.tabs.addTab(self.create_macro_editor_tab(), "Macro Editor")
        self.tabs.addTab(self.create_button_assignment_tab(), "Button Assignment")
        layout.addWidget(self.tabs)

        central_widget.setLayout(layout)

        self.mouse_listener = mouse.Listener(on_click=self.on_click, on_move=self.on_move)
        self.mouse_listener.start()

        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.keyboard_listener.start()

    def create_profiles_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.profile_list = QListWidget()
        layout.addWidget(self.profile_list)

        button_layout = QHBoxLayout()
        new_profile_button = QPushButton("New Profile")
        new_profile_button.clicked.connect(self.create_new_profile)
        button_layout.addWidget(new_profile_button)

        edit_profile_button = QPushButton("Edit Profile")
        edit_profile_button.clicked.connect(self.edit_profile)
        button_layout.addWidget(edit_profile_button)

        delete_profile_button = QPushButton("Delete Profile")
        delete_profile_button.clicked.connect(self.delete_profile)
        button_layout.addWidget(delete_profile_button)

        layout.addLayout(button_layout)
        tab.setLayout(layout)
        return tab

    def create_macro_editor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        self.macro_list = QListWidget()
        layout.addWidget(self.macro_list)

        button_layout = QHBoxLayout()
        record_button = QPushButton("Record Macro")
        record_button.clicked.connect(self.toggle_recording)
        button_layout.addWidget(record_button)

        play_button = QPushButton("Play Macro")
        play_button.clicked.connect(self.play_macro)
        button_layout.addWidget(play_button)

        save_button = QPushButton("Save Macro")
        save_button.clicked.connect(self.save_macro)
        button_layout.addWidget(save_button)

        edit_button = QPushButton("Edit Macro")
        edit_button.clicked.connect(self.edit_macro)
        button_layout.addWidget(edit_button)

        layout.addLayout(button_layout)

        # Add delay settings
        delay_layout = QFormLayout()
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 10000)
        self.delay_spinbox.setValue(10)
        self.delay_spinbox.setSuffix(" ms")
        delay_layout.addRow("Delay between actions:", self.delay_spinbox)

        # Add repeat checkbox
        self.repeat_checkbox = QCheckBox("Repeat Macro")
        delay_layout.addRow(self.repeat_checkbox)

        # Add trigger option
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["On Press", "On Release"])
        delay_layout.addRow("Trigger macro:", self.trigger_combo)

        layout.addLayout(delay_layout)

        tab.setLayout(layout)
        return tab

    def create_button_assignment_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        button_group = QGroupBox("Mouse Button Assignments")
        button_layout = QGridLayout()

        buttons = ['left', 'right', 'middle', 'back', 'forward']
        for i, button in enumerate(buttons):
            label = QLabel(f"{button.capitalize()} Button:")
            combo = QComboBox()
            combo.addItem("None")
            if self.current_profile:
                combo.addItems(self.current_profile.macros.keys())
            combo.setCurrentText(self.current_profile.button_assignments.get(button, "None") if self.current_profile else "None")
            combo.currentTextChanged.connect(lambda text, btn=button: self.assign_macro_to_button(btn, text))
            button_layout.addWidget(label, i, 0)
            button_layout.addWidget(combo, i, 1)

        button_group.setLayout(button_layout)
        layout.addWidget(button_group)

        tab.setLayout(layout)
        return tab

    def assign_macro_to_button(self, button, macro_name):
        if self.current_profile:
            if macro_name == "None":
                self.current_profile.button_assignments.pop(button, None)
            else:
                self.current_profile.button_assignments[button] = macro_name
            self.save_profiles()

    def create_new_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Enter profile name:")
        if ok and name:
            profile = Profile(name)
            self.profiles.append(profile)
            self.profile_list.addItem(name)
            self.current_profile = profile
            self.save_profiles()

    def edit_profile(self):
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            return

        profile_name = selected_items[0].text()
        for profile in self.profiles:
            if profile.name == profile_name:
                self.current_profile = profile
                self.macro_list.clear()
                self.macro_list.addItems(profile.macros.keys())
                self.update_button_assignments()
                break

    def update_button_assignments(self):
        assignment_tab = self.tabs.widget(2)
        button_group = assignment_tab.findChild(QGroupBox)
        if button_group:
            for combo in button_group.findChildren(QComboBox):
                combo.clear()
                combo.addItem("None")
                combo.addItems(self.current_profile.macros.keys())
                button = combo.property("button")
                if button:
                    combo.setCurrentText(self.current_profile.button_assignments.get(button, "None"))

    def delete_profile(self):
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            return

        profile_name = selected_items[0].text()
        for profile in self.profiles:
            if profile.name == profile_name:
                self.profiles.remove(profile)
                self.profile_list.takeItem(self.profile_list.row(selected_items[0]))
                if self.current_profile == profile:
                    self.current_profile = None
                    self.macro_list.clear()
                break
        self.save_profiles()

    def toggle_recording(self):
        self.recording = not self.recording
        if self.recording:
            name, ok = QInputDialog.getText(self, "New Macro", "Enter macro name:")
            if ok and name:
                self.current_macro = Macro(name)
                self.current_macro.delay = self.delay_spinbox.value()
                self.current_macro.repeat = self.repeat_checkbox.isChecked()
                self.current_macro.trigger_on_press = self.trigger_combo.currentText() == "On Press"
        else:
            self.save_macro()

    def on_click(self, x, y, button, pressed):
        if self.recording and self.current_macro:
            self.current_macro.actions.append(Action('click', button=button, x=x, y=y, delay=self.current_macro.delay))

    def on_move(self, x, y):
        if self.recording and self.current_macro:
            self.current_macro.actions.append(Action('move', x=x, y=y, delay=self.current_macro.delay))

    def on_key_press(self, key):
        if self.recording and self.current_macro:
            self.current_macro.actions.append(Action('key_press', button=key, delay=self.current_macro.delay))

    def on_key_release(self, key):
        if self.recording and self.current_macro:
            self.current_macro.actions.append(Action('key_release', button=key, delay=self.current_macro.delay))

    def save_macro(self):
        if self.current_macro and self.current_profile:
            self.current_profile.macros[self.current_macro.name] = self.current_macro
            self.macro_list.addItem(self.current_macro.name)
            self.current_macro = None
            self.save_profiles()
            self.update_button_assignments()

    def play_macro(self):
        selected_items = self.macro_list.selectedItems()
        if not selected_items or not self.current_profile:
            return

        macro_name = selected_items[0].text()
        macro = self.current_profile.macros.get(macro_name)
        if not macro:
            return

        self.current_macro = macro
        self.current_macro_index = 0
        self.execute_macro_step()

    def execute_macro_step(self):
        if self.current_macro_index >= len(self.current_macro.actions):
            if self.current_macro.repeat:
                self.current_macro_index = 0
            else:
                self.macro_timer.stop()
                return

        action = self.current_macro.actions[self.current_macro_index]
        if action.type == 'move':
            self.mouse.position = (action.x, action.y)
        elif action.type == 'click':
            self.mouse.position = (action.x, action.y)
            if action.button:
                self.mouse.click(action.button)
        elif action.type == 'key_press':
            self.keyboard.press(action.button)
        elif action.type == 'key_release':
            self.keyboard.release(action.button)
        elif action.type == 'scroll':
            self.mouse.scroll(0, action.scroll_amount)

        self.current_macro_index += 1
        self.macro_timer.start(action.delay)

    def edit_macro(self):
        selected_items = self.macro_list.selectedItems()
        if not selected_items or not self.current_profile:
            return

        macro_name = selected_items[0].text()
        macro = self.current_profile.macros.get(macro_name)
        if not macro:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Macro: {macro_name}")
        layout = QVBoxLayout()

        delay_spinbox = QSpinBox()
        delay_spinbox.setRange(0, 10000)
        delay_spinbox.setValue(macro.delay)
        delay_spinbox.setSuffix(" ms")
        layout.addWidget(QLabel("Delay between actions:"))
        layout.addWidget(delay_spinbox)

        repeat_checkbox = QCheckBox("Repeat Macro")
        repeat_checkbox.setChecked(macro.repeat)
        layout.addWidget(repeat_checkbox)

        trigger_combo = QComboBox()
        trigger_combo.addItems(["On Press", "On Release"])
        trigger_combo.setCurrentText("On Press" if macro.trigger_on_press else "On Release")
        layout.addWidget(QLabel("Trigger macro:"))
        layout.addWidget(trigger_combo)

        action_list = QListWidget()
        for action in macro.actions:
            action_list.addItem(f"{action.type}: {action.button if action.button else ''} "
                                f"{'x=' + str(action.x) + ' y=' + str(action.y) if action.x is not None else ''} "
                                f"{'scroll=' + str(action.scroll_amount) if action.scroll_amount is not None else ''} "
                                f"delay={action.delay}")

        layout.addWidget(QLabel("Actions:"))
        layout.addWidget(action_list)

        edit_action_button = QPushButton("Edit Action")
        edit_action_button.clicked.connect(lambda: self.edit_action(action_list, macro))
        layout.addWidget(edit_action_button)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            macro.delay = delay_spinbox.value()
            macro.repeat = repeat_checkbox.isChecked()
            macro.trigger_on_press = trigger_combo.currentText() == "On Press"
            self.save_profiles()

    def edit_action(self, action_list, macro):
        selected_items = action_list.selectedItems()
        if not selected_items:
            return

        index = action_list.row(selected_items[0])
        action = macro.actions[index]

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Action")
        layout = QVBoxLayout()

        action_type_combo = QComboBox()
        action_type_combo.addItems(['move', 'click', 'key_press', 'key_release', 'scroll'])
        action_type_combo.setCurrentText(action.type)
        layout.addWidget(QLabel("Action Type:"))
        layout.addWidget(action_type_combo)

        button_input = QLineEdit(str(action.button) if action.button else '')
        layout.addWidget(QLabel("Button:"))
        layout.addWidget(button_input)

        x_input = QSpinBox()
        x_input.setRange(-10000, 10000)
        x_input.setValue(action.x if action.x is not None else 0)
        layout.addWidget(QLabel("X:"))
        layout.addWidget(x_input)

        y_input = QSpinBox()
        y_input.setRange(-10000, 10000)
        y_input.setValue(action.y if action.y is not None else 0)
        layout.addWidget(QLabel("Y:"))
        layout.addWidget(y_input)

        scroll_input = QSpinBox()
        scroll_input.setRange(-100, 100)
        scroll_input.setValue(action.scroll_amount if action.scroll_amount is not None else 0)
        layout.addWidget(QLabel("Scroll Amount:"))
        layout.addWidget(scroll_input)

        delay_input = QSpinBox()
        delay_input.setRange(0, 10000)
        delay_input.setValue(action.delay)
        delay_input.setSuffix(" ms")
        layout.addWidget(QLabel("Delay:"))
        layout.addWidget(delay_input)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            action.type = action_type_combo.currentText()
            action.button = button_input.text() if button_input.text() else None
            action.x = x_input.value() if action.type in ['move', 'click'] else None
            action.y = y_input.value() if action.type in ['move', 'click'] else None
            action.scroll_amount = scroll_input.value() if action.type == 'scroll' else None
            action.delay = delay_input.value()

            action_list.item(index).setText(f"{action.type}: {action.button if action.button else ''} "
                                            f"{'x=' + str(action.x) + ' y=' + str(action.y) if action.x is not None else ''} "
                                            f"{'scroll=' + str(action.scroll_amount) if action.scroll_amount is not None else ''} "
                                            f"delay={action.delay}")
            self.save_profiles()

    def save_profiles(self):
        data = []
        for profile in self.profiles:
            profile_data = {
                'name': profile.name,
                'macros': {},
                'button_assignments': profile.button_assignments
            }
            for macro_name, macro in profile.macros.items():
                profile_data['macros'][macro_name] = {
                    'actions': [vars(action) for action in macro.actions],
                    'repeat': macro.repeat,
                    'trigger_on_press': macro.trigger_on_press,
                    'delay': macro.delay
                }
            data.append(profile_data)

        with open('ts4windows_profiles.json', 'w') as f:
            json.dump(data, f)

    def load_profiles(self):
        try:
            with open('ts4windows_profiles.json', 'r') as f:
                data = json.load(f)

            for profile_data in data:
                profile = Profile(profile_data['name'])
                for macro_name, macro_data in profile_data['macros'].items():
                    macro = Macro(macro_name)
                    macro.actions = [Action(**action_data) for action_data in macro_data['actions']]
                    macro.repeat = macro_data['repeat']
                    macro.trigger_on_press = macro_data['trigger_on_press']
                    macro.delay = macro_data.get('delay', 10)  # Default to 10ms if not specified
                    profile.macros[macro_name] = macro
                profile.button_assignments = profile_data.get('button_assignments', {})
                self.profiles.append(profile)
                self.profile_list.addItem(profile.name)
        except FileNotFoundError:
            pass

    def show_login(self):
        dialog = LoginDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username = dialog.username.text()
            password = dialog.password.text()
            if self.authenticate(username, password):
                return True
            else:
                QMessageBox.warning(self, "Login Failed", "Invalid username or password")
        return False

    def authenticate(self, username, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        return self.users.get(username) == hashed_password

    def load_users(self):
        try:
            with open('users.json', 'r') as f:
                self.users = json.load(f)
        except FileNotFoundError:
            self.users = {}

    def save_users(self):
        with open('users.json', 'w') as f:
            json.dump(self.users, f)

    def add_user(self, username, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        self.users[username] = hashed_password
        self.save_users()

    def closeEvent(self, event):
        self.save_profiles()
        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = TS4Windows()
    window.show()
    window.load_profiles()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()