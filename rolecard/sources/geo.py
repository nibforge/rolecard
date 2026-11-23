"""Is a search location in Spain? (spec 003, decision D). A plain list of names, folded:
the country, its autonomous communities, provinces, capitals and large cities."""

from __future__ import annotations

from rolecard.services.dedup import fold

_PLACES = """
España, Spain, Andalucía, Andalusia, Aragón, Asturias, Baleares, Illes Balears,
Canarias, Canary Islands, Cantabria, Castilla y León, Castilla-La Mancha, Cataluña,
Catalunya, Catalonia, Comunidad Valenciana, Comunitat Valenciana, Extremadura, Galicia,
La Rioja, Madrid, Murcia, Navarra, Nafarroa, País Vasco, Euskadi, Basque Country, Ceuta,
Melilla, A Coruña, La Coruña, Álava, Araba, Albacete, Alicante, Alacant, Almería, Ávila,
Badajoz, Barcelona, Burgos, Cáceres, Cádiz, Castellón, Castelló, Ciudad Real, Córdoba,
Cuenca, Girona, Gerona, Granada, Guadalajara, Guipúzcoa, Gipuzkoa, Huelva, Huesca, Jaén,
León, Lleida, Lérida, Lugo, Málaga, Ourense, Orense, Oviedo, Palencia, Palma de Mallorca,
Pamplona, Iruña, Pontevedra, Salamanca, Segovia, Sevilla, Seville, Soria, Tarragona,
Teruel, Toledo, Valencia, Valladolid, Vizcaya, Bizkaia, Zamora, Zaragoza, Santander,
Logroño, Bilbao, San Sebastián, Donostia, Vitoria, Gasteiz, Santa Cruz de Tenerife,
Tenerife, Las Palmas, Gran Canaria, Mallorca, Ibiza, Eivissa, Menorca, Vigo, Gijón,
L'Hospitalet, Hospitalet de Llobregat, Elche, Elx, Cartagena, Jerez de la Frontera,
Marbella, Terrassa, Sabadell, Badalona, Móstoles, Alcalá de Henares, Fuenlabrada,
Leganés, Getafe, Alcorcón, Torrejón de Ardoz, Santiago de Compostela, Ferrol, Reus,
Mataró, Sant Cugat, Granollers, Manresa
"""

# Countries and states that share city names with Spain ("Córdoba, Argentina",
# "Toledo, Ohio"): naming one of them, and not Spain itself, means the place is not here.
_ELSEWHERE = """
Mexico, Argentina, Chile, Colombia, Peru, Venezuela, Ecuador, Bolivia, Paraguay,
Uruguay, Cuba, Puerto Rico, Costa Rica, Panama, Honduras, Guatemala, Nicaragua,
El Salvador, Dominican Republic, Republica Dominicana, Philippines, Filipinas, Brazil,
Brasil, Portugal, France, Francia, Italy, Italia, Germany, Alemania, United Kingdom, UK,
USA, US, United States, Estados Unidos, Ohio, Texas, California, Florida, Illinois,
Pennsylvania, Kentucky, Iowa, Missouri, Indiana, Michigan, Colorado, Arizona, Nevada
"""


def _names(text: str) -> frozenset[str]:
    return frozenset(fold(name) for name in text.split(",") if fold(name))


_NAMES, _OTHER, _COUNTRY = _names(_PLACES), _names(_ELSEWHERE), _names("España, Spain")


def _names_any(haystack: str, names: frozenset[str]) -> bool:
    return any(f" {name} " in haystack for name in names)


def in_spain(location: str) -> bool:
    """True if ``location`` names Spain or a place in it (whole words, folded), and not
    another country or state that has a place with the same name."""
    haystack = f" {fold(location)} "
    if _names_any(haystack, _OTHER) and not _names_any(haystack, _COUNTRY):
        return False
    return _names_any(haystack, _NAMES)
