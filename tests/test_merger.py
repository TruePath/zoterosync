import zoterosync.merge
import pytest
import zoterosync
import itertools
import copy
from zoterosync import Person
from zoterosync import Creator


creators_first_data = [{'creatorType': 'author', 'firstName': 'Dhruva R.', 'lastName': 'Chakrabarti'},
                  {'creatorType': 'author', 'firstName': 'Prithviraj', 'lastName': 'Banerjee'}]

creators_second_data = [{'creatorType': 'editor', 'firstName': 'V . ', 'lastName': ' Cate'},
                   {'creatorType': 'contributor', 'firstName': ' t ', 'lastName': 'Gross'}]
creators_second_data_alt = [{'creatorType': 'editor', 'firstName': 'vlad', 'lastName': 'cate'},
                   {'creatorType': 'contributor', 'firstName': 'Tomas M', 'lastName': ' Gross'}]

creators_zero_data = [{'creatorType': 'author', 'firstName': 'Robert S', 'lastName': 'Cartwright'},
                 {'creatorType': 'author', 'firstName': 'Keith D', 'lastName': 'Cooper'}]

creators_fourth_data = [{'creatorType': 'author', 'firstName': 'David M', 'lastName': 'Lane'},
                   {'creatorType': 'author', 'firstName': 'Matthew', 'lastName': 'Flatt'},
                   {'creatorType': 'author', 'firstName': 'Matthew', 'lastName': 'Flatt'}]

creators_zero_alt_data = [{'creatorType': 'author', 'firstName': 'Robert', 'lastName': 'Cartwright'},
                     {'creatorType': 'author', 'firstName': 'Mattias', 'lastName': 'Felleisen'}]


@pytest.fixture
def creator_first():
    return [Creator(d) for d in creators_first_data]


@pytest.fixture
def creator_second():
    return [Creator(d) for d in creators_second_data]


@pytest.fixture
def persons_second_with_alt():
    return [Creator(d).creator for d in itertools.chain(creators_second_data, creators_second_data_alt)]


def test_creator_person(creator_first, creator_second):
    creators = creator_first
    assert creators[0].type == 'author'
    assert creators[1].type == 'author'
    assert len(creators) == 2
    dhruva = creators[0].creator
    assert dhruva.firstname == 'Dhruva R.'
    assert dhruva.lastname == 'Chakrabarti'
    assert dhruva.first_initial == 'D'
    assert dhruva.first_initial_only() is False
    clean_dhruva = dhruva.clean()
    assert clean_dhruva.firstname == 'Dhruva R.'
    assert clean_dhruva.lastname == 'Chakrabarti'
    creators = creator_second
    assert creators[0].type == 'editor'
    assert creators[1].type == 'contributor'
    assert len(creators) == 2
    cate = creators[0].creator
    assert cate.firstname == 'V . '
    assert cate.lastname == ' Cate'
    assert cate.first_initial == 'V'
    assert cate.first_initial_only() is True
    clean_cate = cate.clean()
    assert clean_cate.firstname == 'V.'
    assert clean_cate.lastname == 'Cate'
    gross = creators[1].creator
    assert gross.firstname == ' t '
    assert gross.lastname == 'Gross'
    assert gross.first_initial == 'T'
    assert gross.first_initial_only() is True
    clean_gross = gross.clean()
    assert clean_gross.firstname == 'T.'
    assert clean_gross.lastname == 'Gross'


def test_pair_persons(persons_second_with_alt):
    persons = persons_second_with_alt
    cate = persons[0]
    cate_alt = persons[2]
    gross = persons[1]
    gross_alt = persons[3]
    assert cate_alt.first_initial_only() is False
    assert cate_alt.first_initial == 'V'
    assert cate.same(cate_alt)
    assert cate_alt.same(cate)
    assert gross.same(gross_alt)
    assert gross_alt.same(gross)
    assert not cate.same(gross)
    assert not cate.same(gross_alt)
    best_cate = Person.best_punct(cate_alt.clean(), cate.clean())
    best_gross = Person.best_punct(gross_alt.clean(), gross.clean())
    assert best_cate.firstname == 'V.'
    assert best_gross.firstname == 'Tomas M.'
    merge_cate = Person.merge(cate, cate_alt)
    merge_gross = Person.merge(gross, gross_alt)
    assert merge_cate.firstname == 'Vlad'
    assert merge_cate.lastname == 'Cate'
    assert merge_gross.firstname == 'Tomas M.'
