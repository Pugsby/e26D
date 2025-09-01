```
            ░██████   ░██████  ░███████   
           ░██   ░██ ░██   ░██ ░██   ░██  
 ░███████        ░██ ░██       ░██    ░██ 
░██    ░██   ░█████  ░███████  ░██    ░██ 
░█████████  ░██      ░██   ░██ ░██    ░██ 
░██        ░██       ░██   ░██ ░██   ░██  
 ░███████  ░████████  ░██████  ░███████   
 ```
 e26D - The web-terminal based e621 client.
## Usage
This is meant to be used on a browser, you can use it from this url:<b>
https://main-frankly-vervet.ngrok-free.app/
### Self-hosting
Of course, you can host this yourself.
#### Requirements
- Python
- pip
- Pillow (pip)
- Requests (pip)
- Linux
#### How to host
Once you've copied the repo, execute `cd path/to/e26D` and `python ./main.py` (Works for most operating systems.)<br>
It would be smart to create a symlink to a external drive for the cache. If you're on linux, do this command: `ln -s /run/media/[username]/[drive name] ./database`, replace [username] with your username.<br>
After running main.py, if you want to host it online, you can either forward port "6767" on your router, then create a account at https://ngrok.com/ and follow the instructions. (ngrok is already downloaded with the repo, run ./ngrok instead of typing just ngrok)<br>
If you would like to delete the cache, execute `rm -r ./database/*`.
## Credits
e26D comes with some applications, including:
- ngrok https://github.com/NGROK
- ascii-image-converter https://github.com/TheZoraiz/ascii-image-converter
## Why do I need linux!? 😡
You need linux so ascii-image-converter will work, without it, images won't display on the website.
## Contributions
Please contribute, I'm only one person and it's extremely hard to create such a big project (as someone who barely knows backend.)<br>
I'm suprised I got to this point, I thought this was just gonna be another unfinished project in my Documents folder.
