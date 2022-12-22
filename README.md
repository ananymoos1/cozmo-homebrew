# cozmo-homebrew
This repository demonstrates or shows how you can control and execute scripts on Cozmo, a robot, without a mobile device. A majority of the scripts use the 'pycozmo' module.
# Requirements:

**Python 3.6.0 or newer (with PATH ticked on)**

**Pillow 6.0.0 - Python image library**

**FlatBuffers - serialization library**

**dpkt - TCP/IP packet parsing library**

**pycozmo - Unofficial Cozmo API**

# I installed the latest version of Python, how do I get this working?
## Connect to Cozmo ##
1. You have to connect to Cozmo's WiFi through your computer. 
2. Open the WiFi Settings Menu and on your PC. This may vary depending on your operating system and hardware.
3. Look for a WiFi network named "Cozmo_XXXXXX". The "X" varies on your Cozmo.
4. Click the network and type in the password and then hit enter.
5. Wait around 3-5 seconds and then click off and let it automatically connect.
6. Go back to the WiFi Settings Menu and if you see the currently connected network as "Cozmo_XXXXXX" then that means you are connected.
## Installing the requirements ##
(You have to reconnect to your WiFi to do this step)
1. Open your terminal or your command prompt into the folder that you have the repository in, or the "requirements.txt" file.
2. Type ```python3 -m pip install -U -r requirements.txt```
3. After installing, it will show the current path of your PC blinking.
## Executing a script ##
1. Connect to Cozmo's WiFi.
2. Open your terminal into the Scripts folder of the repository.
3. Type ```py video.py``` into the terminal and click enter.
4. After clicking enter, you should see a pixelated video live from Cozmo's camera on Cozmo's screen.
5. Now that you executed a script, you can execute other scripts in the scripts folder by replacing "video.py" with the file name of the script you want to use.
## Credits ##
1. Zayfod.
2. Creators of the scripts in the Scripts folder of the repository.
