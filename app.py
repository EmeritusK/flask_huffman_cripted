from flask import Flask, request, jsonify, send_file
from graphviz import Digraph
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["http://localhost:4200"])

# =================== FUNCIONES ===================

def contar_frecuencias(text):
    frecuencias = {}
    for caracter in text:
        frecuencias[caracter] = frecuencias.get(caracter, 0) + 1
    return sorted(frecuencias.items(), key=lambda x: x[1])
    for caracter in text:
        frecuencias[caracter] = frecuencias.get(caracter, 0) + 1
    return sorted(frecuencias.items(), key=lambda x: x[1])

def construir_arbol_huffman(frecuencias_ordenadas):
    nodos = [(char, freq, None, None) for char, freq in frecuencias_ordenadas]
    while len(nodos) > 1:
        nodos = sorted(nodos, key=lambda x: x[1])
        nodo1 = nodos.pop(0)
        nodo2 = nodos.pop(0)
        nuevo_nodo = (nodo1[0]+nodo2[0], nodo1[1]+nodo2[1], nodo1, nodo2)
        nodos.append(nuevo_nodo)
    return nodos[0]

def generar_codigos(nodo, prefijo="", codigos={}):
    if nodo[2] is None and nodo[3] is None:
        codigos[nodo[0]] = prefijo
    else:
        if nodo[2]:
            generar_codigos(nodo[2], prefijo + "0", codigos)
        if nodo[3]:
            generar_codigos(nodo[3], prefijo + "1", codigos)
    return codigos

def cifrar(texto, codigos):
    return ''.join([codigos[c] for c in texto])

def descifrar(codigo_binario, arbol):
    resultado = ""
    nodo = arbol
    for bit in codigo_binario:
        nodo = nodo[2] if bit == "0" else nodo[3]
        if nodo[2] is None and nodo[3] is None:
            resultado += nodo[0]
            nodo = arbol
    return resultado

def graficar_arbol(nodo, filename="huffman_tree"):
    def _graficar(nodo, dot=None, contador=[0]):
        if dot is None:
            dot = Digraph()
            dot.attr(rankdir='TB')

        idx = str(contador[0])
        label = f"{nodo[1]}"
        if nodo[2] is None and nodo[3] is None:
            label = f"{nodo[0]}\n{nodo[1]}"
        dot.node(idx, label)
        
        actual_idx = contador[0]
        contador[0] += 1

        if nodo[2]:
            izquierda_idx = contador[0]
            _graficar(nodo[2], dot, contador)
            dot.edge(str(actual_idx), str(izquierda_idx), label="0")
        if nodo[3]:
            derecha_idx = contador[0]
            _graficar(nodo[3], dot, contador)
            dot.edge(str(actual_idx), str(derecha_idx), label="1")
        
        return dot

    dot = _graficar(nodo)
    dot.render(filename, format="png", cleanup=True)

# =================== FUNCIÓN PRINCIPAL ===================

def cifrar_texto(texto, prefix=""):
    frecuencias = contar_frecuencias(texto)
    arbol = construir_arbol_huffman(frecuencias)
    codigos = generar_codigos(arbol)
    cifrado = cifrar(texto, codigos)
    descifrado = descifrar(cifrado, arbol)
    
    # Generar imagen con prefijo único
    image_filename = f"{prefix}huffman_tree" if prefix else "huffman_tree"
    graficar_arbol(arbol, filename=image_filename)
    
    return {
        "frecuencias": frecuencias,
        "codigos": codigos,
        "cifrado": cifrado,
        "descifrado": descifrado,
        "imagen": f"{image_filename}.png"
    }

# =================== FLASK ===================

def serializar_arbol(nodo):
    if nodo[2] is None and nodo[3] is None:
        return {'char': nodo[0], 'freq': nodo[1], 'left': None, 'right': None}
    return {
        'char': nodo[0],
        'freq': nodo[1],
        'left': serializar_arbol(nodo[2]),
        'right': serializar_arbol(nodo[3])
    }

@app.route("/cifrar_usuario", methods=["POST"])
def api_cifrar_usuario():
    data = request.get_json()
    
    if not data or not all(key in data for key in ['name', 'lastname', 'email']):
        return jsonify({"error": "Se requieren name, lastname y email"}), 400
    
    resultados = {}
    imagenes = []
    arboles = {}  # Nuevo: almacenar los árboles serializados
    
    for campo in ['name', 'lastname', 'email']:
        texto = data[campo]
        if not texto:
            return jsonify({"error": f"El campo {campo} no puede estar vacío"}), 400
        
        resultado = cifrar_texto(texto, prefix=f"{campo}_")
        resultados[campo] = {
            "texto_original": texto,
            "texto_cifrado": resultado["cifrado"],
            "texto_descifrado": resultado["descifrado"],
            "codigos": resultado["codigos"]
        }
        imagenes.append(resultado["imagen"])
        
        # Serializar el árbol y guardarlo
        frecuencias = contar_frecuencias(texto)
        arbol = construir_arbol_huffman(frecuencias)
        arboles[campo] = serializar_arbol(arbol)  # Árbol serializado
    
    return jsonify({
        "usuario": resultados,
        "imagenes": imagenes,
        "arboles": arboles  # Nuevo: incluir los árboles en la respuesta
    })

def deserializar_arbol(nodo_serializado):
    if nodo_serializado['left'] is None and nodo_serializado['right'] is None:
        return (nodo_serializado['char'], nodo_serializado['freq'], None, None)
    return (
        nodo_serializado['char'],
        nodo_serializado['freq'],
        deserializar_arbol(nodo_serializado['left']),
        deserializar_arbol(nodo_serializado['right'])
    )

@app.route("/descifrar", methods=["POST"])
def api_descifrar():
    data = request.get_json()
    
    if not data or 'texto_cifrado' not in data or 'arbol' not in data:
        return jsonify({"error": "Se requieren 'texto_cifrado' y 'arbol'"}), 400
    
    try:
        texto_cifrado = data['texto_cifrado']
        arbol_serializado = data['arbol']
        
        # Reconstruir el árbol desde la versión serializada
        arbol = deserializar_arbol(arbol_serializado)
        
        # Descifrar el texto
        texto_descifrado = descifrar(texto_cifrado, arbol)
        
        return jsonify({
            "texto_cifrado": texto_cifrado,
            "texto_descifrado": texto_descifrado
        })
        
    except Exception as e:
        return jsonify({"error": f"Error al descifrar: {str(e)}"}), 500

@app.route("/imagen/<nombre_imagen>")
def api_imagen(nombre_imagen):
    if not os.path.exists(nombre_imagen):
        return jsonify({"error": "Imagen no encontrada"}), 404
    return send_file(nombre_imagen, mimetype='image/png')

# =================== EJECUTAR ===================

if __name__ == "__main__":
    app.run(debug=True)