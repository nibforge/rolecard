"""Locations in Spain (decision D, R16)."""

import pytest

from rolecard.sources.geo import in_spain


@pytest.mark.parametrize("location", [
    "Barcelona", "barcelona, españa", "MÁLAGA", "Spain", "Remoto (España)",
    "San Sebastián", "A Coruña", "L'Hospitalet de Llobregat", "Comunidad de Madrid",
    "Remote (Spain, Portugal)",
])
def test_places_in_spain(location):
    assert in_spain(location)


@pytest.mark.parametrize("location", ["", "Berlin", "Europe", "Worldwide", "Lisboa",
                                      "Madridejos-style typo: Madridx", "Leonberg",
                                      "Guadalajara, Mexico", "Córdoba, Argentina",
                                      "Toledo, Ohio", "Valencia, Venezuela",
                                      "Granada Nicaragua", "Merida, México"])
def test_places_outside_spain(location):
    assert not in_spain(location)
