import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
from datetime import datetime
import threading
import queue
import binascii
import webbrowser

class SerialGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Command Interface")
        self.serial_port = None
        self.is_connected = False
        self.message_queue = queue.Queue()
        
        # Predefined commands
        self.commands = [
            "help", "ver", "tempTest", "blinkLed", "ping"
        ]
        
        self.setup_gui()
        self.update_ports()
        
        # Configure weight for resizing
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        
        # Start the message processing thread
        self.running = True
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.process_messages()

    def setup_gui(self):
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection Settings", padding=10)
        conn_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        conn_frame.grid_columnconfigure(1, weight=1)
        
        # Port selection
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, padx=5)
        self.port_combo = ttk.Combobox(conn_frame, width=20)
        self.port_combo.grid(row=0, column=1, padx=5, sticky="ew")
        
        # Refresh ports button
        ttk.Button(conn_frame, text="↻", width=3, 
                  command=self.update_ports).grid(row=0, column=2, padx=5)
        
        # Baudrate selection
        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=3, padx=5)
        self.baud_combo = ttk.Combobox(conn_frame, width=10, 
                                      values=[9600, 19200, 115200])
        self.baud_combo.set(115200)
        self.baud_combo.grid(row=0, column=4, padx=5)
        
        # Line ending selection
        ttk.Label(conn_frame, text="Line Ending:").grid(row=0, column=5, padx=5)
        self.line_ending_var = tk.StringVar(value="CR+LF (\r\n)")
        self.line_ending_combo = ttk.Combobox(conn_frame, 
                                            textvariable=self.line_ending_var,
                                            values=["CR+LF (\r\n)", "CR (\r)", 
                                                   "LF (\n)", "None"],
                                            width=15)
        self.line_ending_combo.grid(row=0, column=6, padx=5)
        self.line_ending_combo.set("LF (\n)")
        
        # Connect button
        self.connect_btn = ttk.Button(conn_frame, text="Connect", 
                                    command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=7, padx=5)
        
        # Command Frame
        cmd_frame = ttk.LabelFrame(self.root, text="Commands", padding=10)
        cmd_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        cmd_frame.grid_columnconfigure(1, weight=1)
        
        # Quick commands
        quick_cmd_frame = ttk.Frame(cmd_frame)
        quick_cmd_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(quick_cmd_frame, text="Quick Commands:").grid(row=0, column=0, padx=5)
        
        for i, cmd in enumerate(self.commands):
            ttk.Button(quick_cmd_frame, text=cmd, 
                      command=lambda c=cmd: self.send_command(c)).grid(row=0, column=i+1, padx=2)
        
        # Command entry
        ttk.Label(cmd_frame, text="Command:").grid(row=1, column=0, padx=5, pady=5)
        self.cmd_entry = ttk.Entry(cmd_frame)
        self.cmd_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.cmd_entry.bind('<Return>', lambda e: self.send_command(self.cmd_entry.get()))
        
        send_btn = ttk.Button(cmd_frame, text="Send", 
                             command=lambda: self.send_command(self.cmd_entry.get()))
        send_btn.grid(row=1, column=2, padx=5)
        
        # Console Frame
        console_frame = ttk.LabelFrame(self.root, text="Console", padding=10)
        console_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(0, weight=1)
        
        # Console output
        self.console = scrolledtext.ScrolledText(console_frame, wrap=tk.WORD)
        self.console.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Clear console button
        ttk.Button(console_frame, text="Clear Console", 
                  command=self.clear_console).grid(row=1, column=0, pady=5)        

    def update_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])

    def toggle_connection(self):
        if not self.is_connected:
            try:
                port = self.port_combo.get()
                baud = int(self.baud_combo.get())
                self.serial_port = serial.Serial(port, baud, timeout=0.1)
                self.is_connected = True
                self.connect_btn.configure(text="Disconnect")
                self.log_message(f"Connected to {port} at {baud} baud")
                
                # Start reading thread
                self.read_thread = threading.Thread(target=self.read_serial)
                self.read_thread.daemon = True
                self.read_thread.start()
                
            except Exception as e:
                self.log_message(f"Connection error: {str(e)}", "red")
        else:
            self.disconnect()

    def disconnect(self):
        if self.serial_port:
            self.serial_port.close()
        self.is_connected = False
        self.connect_btn.configure(text="Connect")
        self.log_message("Disconnected")

    def send_command(self, command):
        if not command:
            return
            
        if not self.is_connected:
            self.log_message("Error: Not connected", "red")
            return
            
        try:
            # Add line ending
            line_ending = self.line_ending_var.get()
            if line_ending == "CR+LF (\r\n)":
                end = "\r\n"
            elif line_ending == "CR (\r)":
                end = "\r"
            elif line_ending == "LF (\n)":
                end = "\n"
            else:
                end = ""
                
            command_with_ending = f"{command}{end}"
            bytes_to_send = command_with_ending.encode()
            
            # Log the exact bytes being sent
            hex_sent = ' '.join(hex(b)[2:].zfill(2) for b in bytes_to_send)
            #self.log_message(f"Sent (hex): {hex_sent}", "gray")
            
            self.serial_port.write(bytes_to_send)
            self.log_message(f"Sent: {command}", "blue")
            self.cmd_entry.delete(0, tk.END)
        except Exception as e:
            self.log_message(f"Send error: {str(e)}", "red")

    def read_serial(self):
        while self.is_connected and self.running:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline()
                    if data:
                        text = data.decode(errors='replace').strip()
                        hex_received = ' '.join(hex(b)[2:].zfill(2) for b in data)
                        if text:
                            self.message_queue.put(("Received: " + text, "green"))
                            #self.message_queue.put(("Received (hex): " + hex_received, "gray"))
            except Exception as e:
                self.message_queue.put((f"Read error: {str(e)}", "red"))
                break

    def process_messages(self):
        while not self.message_queue.empty():
            message, color = self.message_queue.get()
            self.log_message(message, color)
        self.root.after(100, self.process_messages)

    def log_message(self, message, color="black"):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.console.tag_config(color, foreground=color)
        self.console.insert(tk.END, f"[{timestamp}] {message}\n", color)
        self.console.see(tk.END)

    def clear_console(self):
        self.console.delete(1.0, tk.END)

    def on_closing(self):
        self.running = False
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    # Set minimum window size
    root.minsize(800, 600)
    app = SerialGUI(root)
    root.mainloop()