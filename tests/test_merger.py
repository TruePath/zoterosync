import zoterosync.merge
import pytest
import zoterosync
import itertools
import copy
from zoterosync import Person
from zoterosync import Creator
from zoterosync.merge import ZoteroDocumentMerger
from zoterosync.merge import SimpleZDocMerger

creators_first_data = [{'creatorType': 'author', 'firstName': 'Dhruva R.', 'lastName': 'Chakrabarti'},
                       {'creatorType': 'author', 'firstName': 'Prithviraj', 'lastName': 'Banerjee'}]

creators_second_data = [{'creatorType': 'editor', 'firstName': 'V . ', 'lastName': ' Cate'},
                        {'creatorType': 'translator', 'firstName': ' t ', 'lastName': 'Gross'}]
creators_second_data_alt = [{'creatorType': 'editor', 'firstName': 'vlad', 'lastName': 'cate'},
                            {'creatorType': 'translator', 'firstName': 'Tomas M', 'lastName': ' Gross'}]

creators_zero_data = [{'creatorType': 'contributor', 'firstName': 'Robert S', 'lastName': 'cartwright'},
                      {'creatorType': 'contributor', 'firstName': 'Keith D', 'lastName': 'Cooper'}]

creators_fourth_data = [{'creatorType': 'author', 'firstName': 'David M', 'lastName': 'Lane'},
                        {'creatorType': 'author', 'firstName': 'Matthew', 'lastName': 'Flatt'},
                        {'creatorType': 'author', 'firstName': 'Matthew', 'lastName': 'Flatt'}]

creators_zero_alt_data = [{'creatorType': 'author', 'firstName': 'Robert', 'lastName': 'Cartwright'},
                          {'creatorType': 'author', 'firstName': 'KD', 'lastName': 'cooper'}]


@pytest.fixture
def creator_first():
    return [Creator(d) for d in creators_first_data]


@pytest.fixture
def creator_second():
    return [Creator(d) for d in creators_second_data]


@pytest.fixture
def persons_second_with_alt():
    return [Creator(d).creator for d in itertools.chain(creators_second_data, creators_second_data_alt)]


@pytest.fixture
def creator_challenge():
    return [[Creator(d) for d in list] for list in
            [creators_second_data, creators_second_data_alt, creators_zero_data, creators_zero_alt_data]]


@pytest.fixture
def empty_doc_merger(zoterolocal):
    docmerge = ZoteroDocumentMerger(zoterolocal)
    docmerge._cur_item_type = 'journalArticle'
    return docmerge


@pytest.fixture
def double_doc_simple_merger(zotero_double_doc):
    docmerge = SimpleZDocMerger(zotero_double_doc)
    return docmerge


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
    assert creators[1].type == 'translator'
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
    merge_cate = Person.merge(cate, cate_alt)
    merge_gross = Person.merge(gross, gross_alt)
    assert merge_cate.firstname == 'Vlad'
    assert merge_cate.lastname == 'Cate'
    assert merge_gross.firstname == 'Tomas M.'
    assert merge_gross.lastname == 'Gross'


def test_doc_merger_creator(empty_doc_merger, creator_challenge):
    zmerge = empty_doc_merger
    creators = creator_challenge
    merged = zmerge.merge_creators(creators)
    assert len(merged) == 6
    editors = [c for c in merged if c.type == 'editor']
    assert len(editors) == 1
    merge_cate = editors[0]
    assert merge_cate.firstname == 'Vlad'
    assert merge_cate.lastname == 'Cate'
    trans = [c for c in merged if c.type == 'translator']
    assert len(trans) == 1
    merge_gross = trans[0]
    assert merge_gross.firstname == 'Tomas M.'
    assert merge_gross.lastname == 'Gross'
    authors = [c for c in merged if c.type == 'author']
    contribs = [c for c in merged if c.type == 'contributor']
    assert len(authors) == 2
    assert len(contribs) == 2
    if (authors[0].first_initial == 'R'):
        rob_author = authors[0]
        keith_author = authors[1]
    else:
        rob_author = authors[1]
        keith_author = authors[0]
    if (contribs[0].first_initial == 'R'):
        rob_contrib = contribs[0]
        keith_contrib = contribs[1]
    else:
        rob_contrib = contribs[1]
        keith_contrib = contribs[0]
    assert rob_author.firstname == 'Robert S.'
    assert rob_author.lastname == 'Cartwright'
    assert rob_contrib.firstname == 'Robert S.'
    assert rob_contrib.lastname == 'Cartwright'
    assert keith_author.firstname == 'Keith D.'
    assert keith_author.lastname == 'Cooper'
    assert keith_contrib.firstname == 'Keith D.'
    assert keith_contrib.lastname == 'Cooper'


def test_real_merge(double_doc_simple_merger):
    zmerge = double_doc_simple_merger
    assert len(zmerge._buckets) == 5
    for buck in zmerge._buckets:
        assert len(zmerge._buckets[buck]) == 2

