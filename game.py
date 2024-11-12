from flask import Flask, request, render_template_string, redirect
from flask_socketio import SocketIO, send
import threading
import random
import time

# Serveur principal du jeu
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Serveur de chat
chat_app = Flask(__name__)
chat_app.config['SECRET_KEY'] = 'secret_chat!'
chat_socketio = SocketIO(chat_app, cors_allowed_origins="*")

players = {}  # Stocke les informations des joueurs
player_colors = {}  # Stocke la couleur de chaque joueur
foods = []  # Liste des éléments de nourriture sur la carte
map_size = 5000  # Taille de la carte agrandie pour plus d'exploration
food_count = 300  # Nombre d'éléments de nourriture sur la carte

# Générer des éléments de nourriture au hasard sur la carte
for _ in range(food_count):
    foods.append({'x': random.randint(0, map_size), 'y': random.randint(0, map_size), 'size': 5})

# Template HTML pour choisir un pseudo
HTML_LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Jeu Multijoueur - Connexion</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
      body { font-family: 'Roboto', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: linear-gradient(to right, #0f2027, #203a43, #2c5364); color: white; }
      #login-container { background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3); transition: transform 0.3s ease; }
      #login-container:hover { transform: scale(1.05); }
      input[type="text"] { padding: 15px; margin-bottom: 20px; width: calc(100% - 32px); border: none; border-radius: 8px; font-size: 16px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); }
      button { padding: 15px 30px; border: none; background: #00b09b; color: white; font-size: 16px; border-radius: 8px; cursor: pointer; transition: background 0.3s, transform 0.2s; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }
      button:hover { background: #96c93d; transform: scale(1.05); }
    </style>
  </head>
  <body>
    <div id="login-container">
      <h1>Choisissez votre Pseudo</h1>
      <form method="post" action="/game">
        <input type="text" name="player_name" placeholder="Entrez votre pseudo" required>
        <br>
        <button type="submit">Rejoindre la Partie</button>
      </form>
    </div>
  </body>
</html>
"""

# Template HTML pour le jeu de style agar.io
HTML_GAME_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Jeu Multijoueur - Style Agar.io</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;700&display=swap');
      body { font-family: 'Roboto', sans-serif; margin: 0; overflow: hidden; background: linear-gradient(to right, #1d2671, #c33764); color: white; }
      canvas { background: radial-gradient(circle, #1d1d1d, #121212); display: block; margin: 0 auto; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); border: 3px solid #00b09b; }
      #leaderboard { position: absolute; top: 10px; right: 10px; background: rgba(0, 0, 0, 0.9); color: white; padding: 15px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); width: 220px; }
      #leaderboard h3 { margin: 0 0 10px 0; text-align: center; font-weight: bold; font-size: 18px; }
      #leaderboard ul { list-style: none; padding: 0; margin: 0; }
      #leaderboard ul li { padding: 6px 0; font-size: 16px; display: flex; align-items: center; }
      #leaderboard ul li img { margin-right: 10px; width: 25px; }
      #minimap { position: absolute; top: 20px; left: 20px; width: 200px; height: 200px; background: rgba(0, 0, 0, 0.8); border: 2px solid #00ff00; border-radius: 10px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); }
      #chat { position: absolute; bottom: 20px; left: 20px; width: 350px; max-height: 250px; overflow-y: auto; background: rgba(0, 0, 0, 0.9); color: white; padding: 15px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); font-size: 16px; }
      #chat input { width: calc(100% - 30px); padding: 10px; border: none; border-radius: 10px; margin-top: 10px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); font-size: 16px; }
    </style>
  </head>
  <body>
    <div id="leaderboard">
      <h3>Top 10 Hackers</h3>
      <ul id="leaderboardList"></ul>
    </div>
    <canvas id="minimap"></canvas>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
    <div id="chat">
      <div id="chatMessages"></div>
      <input type="text" id="chatInput" placeholder="Tapez votre message...">
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.min.js"></script>
    <script>
      const canvas = document.getElementById('gameCanvas');
      const ctx = canvas.getContext('2d');
      const minimapCanvas = document.getElementById('minimap');
      const minimapCtx = minimapCanvas.getContext('2d');
      const playerName = '{{ player_name }}';
      const mapSize = {{ map_size }};
      const playerColor = '{{ player_color }}';
      const chatInput = document.getElementById('chatInput');
      const chatMessages = document.getElementById('chatMessages');

      let players = {{ players | tojson }};
      let foods = {{ foods | tojson }};
      const socket = io.connect('http://' + document.domain + ':8080');
      const chatSocket = io.connect('http://' + document.domain + ':443');

      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      minimapCanvas.width = 200;
      minimapCanvas.height = 200;

      const updateInterval = 1; // Intervalle de mise à jour réduit à 1 ms pour améliorer la fluidité
      let movementData = null; // Stocke les données de mouvement pour limiter les appels réseau
      let isSending = false; // Indicateur pour éviter les requêtes multiples simultanées

      window.addEventListener('beforeunload', () => {
        fetch('/disconnect', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: `player_name=${playerName}`,
        });
      });

      function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const currentPlayer = players[playerName];
        if (!currentPlayer) return;
        const zoomFactor = Math.max(0.5, 1 - currentPlayer.size / 500); // Déterminer le niveau de zoom en fonction de la taille du joueur
        ctx.save();
        ctx.scale(zoomFactor, zoomFactor);
        const offsetX = currentPlayer.x - (canvas.width / zoomFactor) / 2;
        const offsetY = currentPlayer.y - (canvas.height / zoomFactor) / 2;

        // Dessiner chaque élément de nourriture (icônes Bitcoin)
        for (let food of foods) {
          const img = new Image();
          img.src = 'https://logospng.org/download/bitcoin/logo-bitcoin-4096.png';
          ctx.drawImage(img, (food.x - offsetX) - 10, (food.y - offsetY) - 10, 20, 20);
        }
        
        // Dessiner chaque joueur (ordinateurs sous forme d'avatars stylisés)
        for (let name in players) {
          let player = players[name];
          const img = new Image();
          img.src = 'https://image.noelshack.com/fichiers/2024/46/2/1731377269-7d.png';
          ctx.drawImage(img, player.x - offsetX - player.size, player.y - offsetY - player.size, player.size * 2, player.size * 2);
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 3;
          ctx.strokeRect(player.x - offsetX - player.size, player.y - offsetY - player.size, player.size * 2, player.size * 2);
        }
        ctx.restore();

        drawMinimap();
      }

      function drawMinimap() {
        minimapCtx.clearRect(0, 0, minimapCanvas.width, minimapCanvas.height);
        const minimapScale = minimapCanvas.width / mapSize;

        // Dessiner les joueurs sur la minimap
        for (let name in players) {
          let player = players[name];
          minimapCtx.beginPath();
          minimapCtx.arc(player.x * minimapScale, player.y * minimapScale, Math.max(2, player.size * minimapScale), 0, Math.PI * 2);
          minimapCtx.fillStyle = player.color;
          minimapCtx.fill();
          minimapCtx.closePath();
        }
      }

      function updateLeaderboard() {
        let leaderboardList = document.getElementById('leaderboardList');
        leaderboardList.innerHTML = '';
        let sortedPlayers = Object.entries(players).sort((a, b) => b[1].size - a[1].size);
        sortedPlayers.slice(0, 10).forEach(([name, player], index) => {
          let li = document.createElement('li');
          if (index === 0) {
            let crownImg = document.createElement('img');
            crownImg.src = 'https://image.noelshack.com/fichiers/2024/46/2/1731379371-design-sans-titre.png';
            li.appendChild(crownImg);
          }
          li.appendChild(document.createTextNode(`${name} - ${player.size}`));
          leaderboardList.appendChild(li);
        });
      }

      function updatePosition(event) {
        const rect = canvas.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const mouseY = event.clientY - rect.top;
        const dx = mouseX - canvas.width / 2;
        const dy = mouseY - canvas.height / 2;
        movementData = { dx, dy };
      }

      async function sendMovement() {
        if (movementData && !isSending) {
          isSending = true; // Empêcher d'autres requêtes simultanées
          const { dx, dy } = movementData;
          const distance = Math.sqrt(dx * dx + dy * dy);
          const speed = Math.max(12, 10 / (players[playerName].size / 30));  // Augmenter la vitesse globale des joueurs
          if (distance > 5 || (dx !== 0 && dy !== 0)) {
            try {
              const response = await fetch('/move', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `player_name=${playerName}&dx=${dx}&dy=${dy}`,
              });
              const data = await response.json();
              players = data.players;
              foods = data.foods;
              updateLeaderboard();
            } catch (error) {
              console.error('Erreur lors de la mise à jour de la position:', error);
            }
          }
          isSending = false; // Autoriser une nouvelle requête
        }
      }

      canvas.addEventListener('mousemove', updatePosition);
      setInterval(sendMovement, updateInterval); // Envoyer les mouvements toutes les 1 ms si des changements sont détectés

      chatInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
          const message = chatInput.value;
          if (message.trim() !== '') {
            // Ajouter le message localement avant de l'envoyer au serveur
            const newMessage = document.createElement('div');
            newMessage.textContent = `${playerName}: ${message}`;
            chatMessages.appendChild(newMessage);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            if (chatMessages.children.length > 5) {
              chatMessages.removeChild(chatMessages.firstChild);
            }
            // Envoyer le message au serveur
            chatSocket.emit('chat_message', { player: playerName, message: message });
            chatInput.value = '';
          }
        }
      });

      chatSocket.on('chat_message', function(data) {
        const newMessage = document.createElement('div');
        newMessage.textContent = `${data.player}: ${data.message}`;
        chatMessages.appendChild(newMessage);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        // Limiter le nombre de messages affichés à 5
        if (chatMessages.children.length > 5) {
          chatMessages.removeChild(chatMessages.firstChild);
        }
      });

      function gameLoop() {
        draw();
        requestAnimationFrame(gameLoop);
      }

      gameLoop();
    </script>
  </body>
</html>
"""

# Fonction pour gérer l'affichage de la carte et le mouvement
@app.route('/', methods=['GET'])
def login():
    return render_template_string(HTML_LOGIN_TEMPLATE)

@app.route('/game', methods=['POST'])
def index():
    player_name = request.form.get('player_name')
    if player_name not in players:
        players[player_name] = {'x': random.randint(50, map_size - 50), 'y': random.randint(50, map_size - 50), 'size': 20}
        player_colors[player_name] = "#%06x" % random.randint(0, 0xFFFFFF)
        players[player_name]['color'] = player_colors[player_name]

    return render_template_string(HTML_GAME_TEMPLATE, player_name=player_name, player_color=players[player_name]['color'], players=players, foods=foods, map_size=map_size)

@app.route('/move', methods=['POST'])
def move():
    player_name = request.form.get('player_name')
    dx = float(request.form.get('dx'))
    dy = float(request.form.get('dy'))

    if player_name in players:
        player = players[player_name]
        speed = max(10, 8 / (player['size'] / 30))  # Augmenter la vitesse globale des joueurs
        magnitude = (dx ** 2 + dy ** 2) ** 0.5
        player['x'] += speed * (dx / magnitude)
        player['y'] += speed * (dy / magnitude)
        player['x'] = min(max(player['x'], 0), map_size)
        player['y'] = min(max(player['y'], 0), map_size)

        # Vérifier la collision avec les éléments de nourriture
        for food in foods[:]:
            distance = ((player['x'] - food['x']) ** 2 + (player['y'] - food['y']) ** 2) ** 0.5
            if distance < player['size'] + food['size']:
                player['size'] += 1  # Augmenter la taille du joueur après avoir mangé la nourriture
                foods.remove(food)
                # Ajouter un nouvel élément de nourriture
                foods.append({'x': random.randint(0, map_size), 'y': random.randint(0, map_size), 'size': 5})

        # Vérifier la collision avec d'autres joueurs
        for other_name, other_player in list(players.items()):
            if other_name != player_name:
                distance = ((player['x'] - other_player['x']) ** 2 + (player['y'] - other_player['y']) ** 2) ** 0.5
                if distance < player['size'] and player['size'] > other_player['size']:
                    player['size'] += other_player['size'] // 2  # Absorber l'autre joueur
                    del players[other_name]

    return {"players": players, "foods": foods}

@app.route('/disconnect', methods=['POST'])
def disconnect():
    player_name = request.form.get('player_name')
    if player_name in players:
        del players[player_name]
    return "", 200

@chat_socketio.on('chat_message')
def handle_chat_message(data):
    chat_socketio.emit('chat_message', data, include_self=False)

# Lancer les serveurs
if __name__ == "__main__":
    threading.Thread(target=lambda: socketio.run(app, host='0.0.0.0', port=8080)).start()
    chat_socketio.run(chat_app, host='0.0.0.0', port=443)
