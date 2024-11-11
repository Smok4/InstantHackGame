from flask import Flask, request, render_template_string, redirect
import threading
import random
import time

app = Flask(__name__)

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
    <style>
      body { font-family: 'Roboto', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: linear-gradient(to right, #0f2027, #203a43, #2c5364); color: white; }
      #login-container { background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2); }
      input[type="text"] { padding: 10px; margin-bottom: 10px; width: calc(100% - 22px); border: none; border-radius: 5px; }
      button { padding: 10px 20px; border: none; background: #00b09b; color: white; border-radius: 5px; cursor: pointer; transition: background 0.3s; }
      button:hover { background: #96c93d; }
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
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;700&display=swap');
      body { font-family: 'Roboto', sans-serif; margin: 0; overflow: hidden; background: #121212; color: white; }
      canvas { background: radial-gradient(circle, #1d1d1d, #121212); display: block; margin: 0 auto; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5); }
      #leaderboard { position: absolute; top: 10px; right: 10px; background: rgba(0, 0, 0, 0.8); color: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3); }
      #leaderboard h3 { margin: 0 0 10px 0; text-align: center; font-weight: bold; }
      #leaderboard ul { list-style: none; padding: 0; margin: 0; }
      #leaderboard ul li { padding: 4px 0; font-size: 14px; }
      #crown { position: absolute; top: 5px; right: 75px; width: 30px; display: none; }
      #minimap { position: absolute; top: 10px; left: 10px; width: 150px; height: 150px; background: rgba(0, 0, 0, 0.8); border: 1px solid #00ff00; border-radius: 5px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3); }
    </style>
  </head>
  <body>
    <img id="crown" src="https://upload.wikimedia.org/wikipedia/commons/4/42/Crown_icon.png" alt="Crown">
    <div id="leaderboard">
      <h3>Top 10 Hackers</h3>
      <ul id="leaderboardList"></ul>
    </div>
    <canvas id="minimap"></canvas>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
    <script>
      const canvas = document.getElementById('gameCanvas');
      const ctx = canvas.getContext('2d');
      const minimapCanvas = document.getElementById('minimap');
      const minimapCtx = minimapCanvas.getContext('2d');
      const playerName = '{{ player_name }}';
      const mapSize = {{ map_size }};
      const playerColor = '{{ player_color }}';
      const crown = document.getElementById('crown');

      let players = {{ players | tojson }};
      let foods = {{ foods | tojson }};

      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      minimapCanvas.width = 150;
      minimapCanvas.height = 150;

      const updateInterval = 1; // Réduction de la charge serveur en ajustant à 50 ms
      let movementData = null; // Stocke les données de mouvement pour limiter les appels réseau
      let isSending = false; // Indicateur pour éviter les requêtes multiples simultanées

      function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const currentPlayer = players[playerName];
        if (!currentPlayer) return;
        const offsetX = currentPlayer.x - canvas.width / 2;
        const offsetY = currentPlayer.y - canvas.height / 2;

        // Dessiner chaque élément de nourriture (petits réseaux)
        for (let food of foods) {
          ctx.beginPath();
          ctx.arc(food.x - offsetX, food.y - offsetY, 8, 0, Math.PI * 2);
          ctx.fillStyle = '#00ff00';
          ctx.fill();
          ctx.closePath();
        }
        
        // Dessiner chaque joueur (ordinateurs sous forme de rectangles stylisés)
        for (let name in players) {
          let player = players[name];
          ctx.beginPath();
          ctx.fillStyle = player.color;
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 3;
          ctx.rect(player.x - offsetX - player.size, player.y - offsetY - player.size, player.size * 2, player.size * 2);
          ctx.fill();
          ctx.stroke();
          ctx.closePath();
        }

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
          li.textContent = `${name} - ${player.size}`;
          leaderboardList.appendChild(li);
        });
        if (sortedPlayers.length > 0 && sortedPlayers[0][0] === playerName) {
          crown.style.display = 'block';
        } else {
          crown.style.display = 'none';
        }
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
          const speed = Math.max(10, 8 / (players[playerName].size / 30));  // Augmenter la vitesse globale des joueurs
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
      setInterval(sendMovement, updateInterval); // Envoyer les mouvements toutes les 50 ms si des changements sont détectés

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

# Lancer le serveur
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, threaded=True)
