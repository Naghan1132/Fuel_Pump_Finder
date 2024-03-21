import folium
import webbrowser as st
from pyroutelib3 import Router


eplb_park = [46.548453, 3.286341]
moulins_mairie = [46.566067 , 3.332859]

router = Router("car")

depart = router.findNode(eplb_park[0],eplb_park[1])
arrivee = router.findNode(moulins_mairie[0],moulins_mairie[1])

status, itineraire = router.doRoute(depart, arrivee)

if status == 'success':
    routeLatLons = list(map(router.nodeLatLon, itineraire)) # liste des points du parcours



carte= folium.Map(location=[(eplb_park[0]+moulins_mairie[0])/2,(eplb_park[1]+moulins_mairie[1])/2],zoom_start=15)
for indice,coord in enumerate(routeLatLons):
    if indice%10==0:
        coord=list(coord)
        folium.Marker(coord).add_to(carte)

itineraire_coordonnees = list(map(router.nodeLatLon, itineraire)) # liste des points du parcours

folium.PolyLine(
    itineraire_coordonnees,
    color="blue",
    weight=2.5,
    opacity=1
).add_to(carte)


carte.save('carte2.html')