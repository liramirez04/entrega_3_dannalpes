from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

#os.environ para despliegue. Descomente cuando ya probó todo local.
client = MongoClient(os.environ["MONGO_URI"])
# TODO: conectarse al cluster Admonsis  


#client = MongoClient("")
# TODO: conectarse a la base de datos Admonsis  
# db = client["ISIS*******"]
db = client["ISIS2304F24202610"]


@app.get("/")
def inicio():
    return {"estado": "API funcionando correctamente"}

# RF1
# POST /reviews
@app.post('/reviews')
def post_review(datos: dict):
    existente = db["Reviews"].find_one({
        "id_reserva": datos["id_reserva"],
        "estado": "publicada"
    })
    if existente:
        return {"error": "Ya existe una reseña para esta reserva"}
    
    datos["fecha_creacion"] = datetime.now()
    datos["estado"] = "publicada"
    datos["destacada"] = False
    datos["votos_utilidad"] = []
    db["Reviews"].insert_one(datos)
    return {"mensaje": "Reseña creada"}

# RF2
# PUT /reviews/{review_id}
@app.put("/reviews/{review_id}")
def editar_review(review_id: str, datos: dict):
    datos["fecha_edicion"] = datetime.now()
    db["Reviews"].update_one(
        {"_id": ObjectId(review_id)},
        {"$set": datos}
    )
    return {"mensaje": "Reseña actualizada"}

# RF3
# DELETE /reviews/{review_id}
@app.delete("/reviews/{review_id}")
def eliminar_review(review_id: str):
    db["Reviews"].update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"estado": "eliminada", "destacada": False}}
    )
    return {"mensaje": "Reseña eliminada"}

# RF4
# GET /hotels/{hotel_id}/reviews
@app.get("/hotels/{hotel_id}/reviews")
def get_reviews_hotel(hotel_id: int):
    reviews = list(db["Reviews"].find(
        {"id_hotel": hotel_id, "estado": "publicada"},
        {"_id": 0}
    ).sort([("destacada", -1), ("fecha_creacion", -1)]))
    return reviews or []
 
# RF5
# POST /reviews/{review_id}/vote
@app.post("/reviews/{review_id}/vote")
def votar_review(review_id: str, datos: dict):
    doc_cliente = datos["documento_identidad_cliente"]
    review = db["Reviews"].find_one({"_id": ObjectId(review_id)})
    if doc_cliente in (review.get("votos_utilidad") or []):
        db["Reviews"].update_one(
            {"_id": ObjectId(review_id)},
            {"$pull": {"votos_utilidad": doc_cliente}}
        )
        return {"mensaje": "Voto removido"}
    else:
        db["Reviews"].update_one(
            {"_id": ObjectId(review_id)},
            {"$addToSet": {"votos_utilidad": doc_cliente}}
        )
        return {"mensaje": "Voto registrado"}
 
 
# RF6
# GET /clients/{doc_identidad}/reviews
@app.get("/clients/{doc_identidad}/reviews")
def get_reviews_cliente(doc_identidad: str):
    resenas = list(db["Reviews"].find(
        {"documento_identidad_cliente": doc_identidad}
    ).sort("fecha_creacion", -1))
    for r in resenas:
        r["_id"] = str(r["_id"])
    return resenas or []
 
 
# RF7
# PUT /reviews/{review_id}/response
@app.put("/reviews/{review_id}/response")
def responder_review(review_id: str, datos: dict):
    db["Reviews"].update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {
            "respuesta_admin": {
                "texto_respuesta": datos["texto_respuesta"],
                "fecha_respuesta": datetime.now()
            }
        }}
    )
    return {"mensaje": "Respuesta guardada"}
 
 
# RF8
# DELETE /admin/reviews/{review_id}
@app.delete("/admin/reviews/{review_id}")
def eliminar_review_admin(review_id: str):
    db["Reviews"].update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"estado": "eliminada", "destacada": False}}
    )
    return {"mensaje": "Reseña eliminada por administrador"}
 
 
# RF9
# PATCH /reviews/{review_id}/feature
@app.patch("/reviews/{review_id}/feature")
def destacar_review(review_id: str):
    review = db["Reviews"].find_one({"_id": ObjectId(review_id)})
    # Quitar destacada actual del mismo hotel
    db["Reviews"].update_many(
        {"id_hotel": review["id_hotel"], "destacada": True},
        {"$set": {"destacada": False}}
    )
    # Marcar la nueva
    db["Reviews"].update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"destacada": True}}
    )
    return {"mensaje": "Reseña destacada"}
 
 
# RFC1
# GET /analytics/top-hotels
@app.get("/analytics/top-hotels")
def top_hoteles(desde: str = "2024-01-01", hasta: str = "2026-12-31"):
    resultado = list(db["Reviews"].aggregate([
        {"$match": {
            "estado": "publicada",
            "fecha_creacion": {
                "$gte": datetime.fromisoformat(desde),
                "$lte": datetime.fromisoformat(hasta + "T23:59:59")
            }
        }},
        {"$group": {
            "_id": "$id_hotel",
            "calificacion_promedio": {"$avg": "$calificacion"},
            "total_resenas": {"$sum": 1}
        }},
        {"$project": {
            "_id": 0,
            "id_hotel": "$_id",
            "calificacion_promedio": {"$round": ["$calificacion_promedio", 2]},
            "total_resenas": 1
        }},
        {"$sort": {"calificacion_promedio": -1, "total_resenas": -1}},
        {"$limit": 10}
    ]))
    return resultado or []
 
 
# RFC2
# GET /analytics/hotel/{hotel_id}/evolution?anio=2025
@app.get("/analytics/hotel/{hotel_id}/evolution")
def evolucion_hotel(hotel_id: int, anio: int = 2025):
    resultado = list(db["Reviews"].aggregate([
        {"$match": {
            "id_hotel": hotel_id,
            "estado": "publicada",
            "$expr": {"$eq": [{"$year": "$fecha_creacion"}, anio]}
        }},
        {"$group": {
            "_id": {
                "anio_mes": {
                    "$dateToString": {"format": "%Y-%m", "date": "$fecha_creacion"}
                }
            },
            "calificacion_promedio": {"$avg": "$calificacion"},
            "total_resenas": {"$sum": 1},
            "cal_minima": {"$min": "$calificacion"},
            "cal_maxima": {"$max": "$calificacion"}
        }},
        {"$project": {
            "_id": 0,
            "mes": "$_id.anio_mes",
            "calificacion_promedio": {"$round": ["$calificacion_promedio", 2]},
            "total_resenas": 1,
            "cal_minima": 1,
            "cal_maxima": 1
        }},
        {"$sort": {"mes": 1}}
    ]))
    return resultado or []
 
 
# RFC3
# Separado en dos endpoints igual que el documento:
# Consulta 1: indicadores por hotel
# GET /analytics/city/hotels?hotel_ids=1,2,3
@app.get("/analytics/city/hotels")
def comparativa_ciudad_hoteles(hotel_ids: str):
    ids = [int(x) for x in hotel_ids.split(",")]
    resultado = list(db["Reviews"].aggregate([
        {"$match": {"id_hotel": {"$in": ids}, "estado": "publicada"}},
        {"$group": {
            "_id": "$id_hotel",
            "calificacion_promedio": {"$avg": "$calificacion"},
            "total_resenas": {"$sum": 1},
            "resenas_con_respuesta": {"$sum": {"$cond": [{"$ifNull": ["$respuesta_admin", False]}, 1, 0]}},
            "resenas_destacadas": {"$sum": {"$cond": [{"$eq": ["$destacada", True]}, 1, 0]}}
        }},
        {"$project": {
            "_id": 0,
            "id_hotel": "$_id",
            "calificacion_promedio": {"$round": ["$calificacion_promedio", 2]},
            "total_resenas": 1,
            "pct_con_respuesta_admin": {"$round": [{"$multiply": [{"$divide": ["$resenas_con_respuesta", "$total_resenas"]}, 100]}, 1]},
            "pct_destacadas": {"$round": [{"$multiply": [{"$divide": ["$resenas_destacadas", "$total_resenas"]}, 100]}, 1]}
        }},
        {"$sort": {"calificacion_promedio": -1}}
    ]))
    return resultado or []
 
 
# Consulta 2: promedio general de la ciudad
# GET /analytics/city/average?hotel_ids=1,2,3
@app.get("/analytics/city/average")
def comparativa_ciudad_promedio(hotel_ids: str):
    ids = [int(x) for x in hotel_ids.split(",")]
    resultado = list(db["Reviews"].aggregate([
        {"$match": {"id_hotel": {"$in": ids}, "estado": "publicada"}},
        {"$group": {
            "_id": None,
            "promedio_ciudad": {"$avg": "$calificacion"}
        }},
        {"$project": {
            "_id": 0,
            "promedio_ciudad": {"$round": ["$promedio_ciudad", 2]}
        }}
    ]))
    return resultado[0] if resultado else {"promedio_ciudad": 0}
 
