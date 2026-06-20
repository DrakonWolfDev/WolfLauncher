# **WolfLauncher**  
A Linux-first DayZ launcher designed to remove the guesswork from joining modded servers.  
DayZ runs surprisingly well on Linux.  
The problem is everything around it.  
Most launchers assume Steam is installed correctly, DayZ is in the expected location, Workshop mods are present, and the server's required mod list matches what you already have installed. When something is missing, you usually find out after the launch fails.  
WolfLauncher takes a different approach.  
Before launching, it checks your Steam installation, verifies DayZ and Workshop locations, compares installed mods against server requirements, and warns about potential problems before handing control to the launcher.  
Built because repeatedly opening terminals and hoping everything was configured correctly got old very quickly.  
## **Features**  
### **Server Management**  
- YAML-based server configuration  
- DNS hostname or IP address support  
- Favourites system  
- Server grouping support  
- Automatic refresh options  
- Persistent settings  
### **Server Monitoring**  
- Live server status checks  
- Player counts and server information  
- Powered by Gamedig  
- Quick diagnostics and troubleshooting tools  
### **Mod Validation**  
- Workshop folder detection  
- Installed versus required mod comparison  
- Missing mod detection  
- Direct Steam Workshop links  
- Launch warnings when required mods are missing  
### **Launch Integration**  
- Native Steam support  
- Flatpak Steam support  
- DayZ installation detection  
- Pre-launch validation checks  
- Launch diagnostics and output logging  
## **Why WolfLauncher Exists**  
The original workflow was a terminal-based launcher script.  
It worked well when everything was configured correctly.  
The problem was discovering when something wasn't.  
Missing mods, incorrect paths, Steam not running, Workshop folders in unexpected locations, or server changes could all result in failed launches and unnecessary troubleshooting.  
WolfLauncher moves those checks to the front of the process.  
Instead of launching first and debugging later, it validates the environment before attempting to start the game.  
## **Current Development Status**  
WolfLauncher is currently in active prototype development.  
Current focus areas include:  
- Improving launch reliability  
- Expanding diagnostics  
- Improving mod management workflows  
- Moving more functionality into the application itself  
- Reducing dependency on external launcher scripts  
## **Installation**  
Install the required dependencies:  
sudo apt update  
sudo apt install python3 python3-venv python3-pip nodejs npm dnsutils libxcb-cursor0  
sudo npm install -g gamedig  
   
Create a virtual environment and start the application:  
python3 -m venv .venv  
source .venv/bin/activate  
pip install -r requirements.txt  
python main.py  
   
## **Launching**  
Configure the path to your existing launcher script.  
Example:  
/home/andi/dayz-launcher.sh  
   
WolfLauncher generates launch commands in the following format:  
bash /home/andi/dayz-launcher.sh -s "HOST:GAMEPORT" -p "QUERYPORT" -n "PLAYER" --launch  
   
Recommended workflow:  
1. Select a server.  
2. Review required mods.  
3. Subscribe to any missing Workshop content.  
4. Return to the server list.  
5. Launch.  
## **Server Configuration**  
Servers are stored in servers.yaml.  
Example:  
servers:  
  - name: Drakon Expansion  
    group: Drakon  
    host: drakonwolf.ddns.net  
    game_port: 3302  
    query_port: 3303  
    favourite: true  
   
The host field may contain either a DNS hostname or an IP address.  
## **Project Documentation**  
Additional project documentation is included in the repository:  
| | |  
|-|-|  
| **File** | **Purpose** |   
| CHANGELOG.md | Version history and release notes |   
| ROADMAP.md | Planned features and future milestones |   
| ARCHITECTURE.md | Design decisions and internal structure |   
| PROJECT_STATE.md | Current development snapshot and handoff notes |   
## **Application Locations**  
### **User Installation**  
~/.local/bin  
~/.local/share/wolflauncher  
   
### **User Configuration**  
~/.config/wolflauncher  
   
### **Future System Installation**  
/opt/wolflauncher  
   
or via a native .deb package.  
## **Roadmap**  
Planned future work includes:  
- Integrated launcher functionality  
- One-click Workshop subscriptions  
- Improved server discovery  
- Enhanced diagnostics  
- Native packaging and installation  
- Expanded Linux distribution support  
## **License**  
License information to be added before first public release.  
   
