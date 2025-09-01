const contentElement = document.getElementById("content");

const logo = [
"            ░██████   ░██████  ░███████   ",
"           ░██   ░██ ░██   ░██ ░██   ░██  ",
" ░███████        ░██ ░██       ░██    ░██ ",
"░██    ░██   ░█████  ░███████  ░██    ░██ ",
"░█████████  ░██      ░██   ░██ ░██    ░██ ",
"░██        ░██       ░██   ░██ ░██   ░██  ",
" ░███████  ░████████  ░██████  ░███████   "
];

const colors = [
'#ff75a2',
'#f0f8ff',
'#be57b4',
'#404040',
'#2f8ba7'
];

const rowColors = {
0: 0, 1: 0,
2: 1,
3: 2,
4: 3, 5: 4, 6: 4
};

let html = logo.map((line, i) => {
const colorIndex = rowColors[i] ?? 0;
return `<span style="color:${colors[colorIndex]}">${line}</span>`;
}).join("<br>");

const day = new Date();
const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const dotw = days[day.getDay()];

html += `
<br>my least favorite day of the week is ${dotw}
═══════════════════════════════════════════
e26D 25w35a - The web-terminal based e621 client.
Please report bugs to <a href="https://www.github.com/pugsby/e26D">github.com/pugsby/e26D</a>
Backend written in Python.
Type "<span style="color:#2f8ba7">e26D</span>" to start.
`;
contentElement.innerHTML = html;
var homeTerm = true
const commandDiv = document.getElementById("command")
document.addEventListener('click', function () {
    if (homeTerm) {
        commandDiv.focus()
    }
})
commandDiv.addEventListener('keypress', function (e) {
    if (e.key == "Enter") {
        setTimeout(function() {
            const commandText = commandDiv.innerHTML.replace(/\r?<br>|\r/g, '');
            console.log(commandText.toLowerCase())
            if (commandText.toLowerCase() == "e26d") {
                homeTerm = false
                e26Dinit()
            }
            contentElement.innerHTML += commandText + " not found.<br>";
            commandDiv.innerHTML = ""
        }, 1)
    }
})
