from flask import Flask, render_template, request, jsonify
import numpy as np
import folium
from geopy.distance import distance
from folium.plugins import HeatMap

def crear_app():

    app = Flask(__name__)

    # Función para mover el humo y simular los incendios
    def move_smoke(grid, incendios, wind_speed_kmh, wind_direction_rad, fire_level, smoke_attenuation_factor, grid_size):
        wind_speed_kms = wind_speed_kmh / 3.6  # Convertir velocidad de km/h a m/s
        smoke_emit_rate = fire_level * 10  # Tasa de emisión de humo, depende del nivel del incendio inicial

        # Ajuste automático de los pasos de tiempo según el nivel del fuego
        time_steps = int(fire_level * 5)  # A mayor nivel de incendio, más pasos de tiempo

        for t in range(time_steps):
            new_grid = np.copy(grid)
            for i in range(1, grid_size-1):
                for j in range(1, grid_size-1):
                    for source_x, source_y in incendios:
                        distance_from_source = np.sqrt((i - source_x)**2 + (j - source_y)**2)
                        # La dispersión se hace más grande proporcional al nivel del incendio
                        dispersion = 0.1 * (grid[i+1, j] + grid[i-1, j] + grid[i, j+1] + grid[i, j-1] - 4 * grid[i, j]) / (1 + distance_from_source**2 * fire_level)
                        directional_factor = 1 + 0.2 * np.cos(np.arctan2(j - source_y, i - source_x) - wind_direction_rad)
                        dispersion *= directional_factor
                        attenuation_factor = max(1 - (t / time_steps), 0.1)
                        dispersion *= attenuation_factor * smoke_attenuation_factor
                        new_grid[i, j] += dispersion
            dx = int(wind_speed_kms * np.cos(wind_direction_rad))
            dy = int(wind_speed_kms * np.sin(wind_direction_rad))
            final_grid = np.zeros_like(grid)
            for i in range(grid_size):
                for j in range(grid_size):
                    new_i = i + dy
                    new_j = j + dx
                    if 0 <= new_i < grid_size and 0 <= new_j < grid_size:
                        final_grid[new_i, new_j] += new_grid[i, j]
            grid = final_grid
            for source_x, source_y in incendios:
                smoke_emit_rate = max(smoke_emit_rate * 0.9, 0)
                grid[source_x, source_y] += smoke_emit_rate
        return grid

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/simulate', methods=['POST'])
    def simulate():
        data = request.json
        lat = float(data['lat'])
        lon = float(data['lon'])
        wind_speed = float(data['wind_speed'])
        wind_direction = float(data['wind_direction'])
        fire_level = int(data['fire_level'])
        num_fires = int(data['num_fires'])
        
        # Definir grid_size
        grid_size = 50
        radius_km = 20
        smoke_attenuation_factor = 0.9
        grid = np.zeros((grid_size, grid_size))
        incendios = [(grid_size // 2, grid_size // 4), (grid_size // 2, grid_size * 3 // 4), (grid_size // 2 - 5, grid_size // 2)]
        incendios = incendios[:num_fires]  # Limitar la cantidad de incendios a los seleccionados
        wind_direction_rad = np.deg2rad(wind_direction)

        for source_x, source_y in incendios:
            grid[source_x, source_y] = fire_level * 100

        concentration_data = move_smoke(grid, incendios, wind_speed, wind_direction_rad, fire_level, smoke_attenuation_factor, grid_size)

        m = folium.Map(location=[lat, lon], zoom_start=7)
        points = [(lat, lon)] * grid_size * grid_size
        heat_data = []

        # Agregar los datos de concentración de humo al heatmap
        for i in range(grid_size):
            for j in range(grid_size):
                concentration = concentration_data[i, j]
                if concentration > 0:
                    lat_shift = lat + (i - grid_size // 2) * 0.01 * fire_level / 5  # Ajustar el desplazamiento al nivel de fuego
                    lon_shift = lon + (j - grid_size // 2) * 0.01 * fire_level / 5
                    heat_data.append([lat_shift, lon_shift, concentration])

        # Verificar la longitud de heat_data
        print(f"Heat data size: {len(heat_data)}")  # Esto nos ayudará a ver si hay datos de humo calculados

        HeatMap(heat_data, radius=15, blur=25, max_zoom=18, min_opacity=0.3, gradient={0: 'gray', 0.6: 'gray', 0.8: 'darkred', 1: 'red'}).add_to(m)

        for source_x, source_y in incendios:
            folium.Marker([lat, lon], popup="Incendio", icon=folium.Icon(color='red')).add_to(m)

        m.save('templates/map.html')
        return jsonify({'map_url': '/map'})

    @app.route('/map')
    def show_map():
        return render_template('map.html')

    return app

if __name__ == '__main__':
    app = crear_app()
    app.run(debug=True)
