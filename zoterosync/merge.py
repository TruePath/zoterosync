import functools
import itertools
from zoterosync.library import Person
from zoterosync.library import Creator
import re


class DuplicateFinder(object):
    """Given a distance function on a list of items finds duplicates using the rule that dist(x,y) < thres
       Makes x, y duplicates then takes transitive closure.  Works on assumption that duplicates occur in clusters
       and don't stretch out over whole space.  dist must satisfy triangle inequality.
    """
    def __init__(self, items, dist, thres):
        self.clusters = dict()
        self.cluster_size = dict()
        self.dist = dist
        self.thres = thres
        self.process(items)

    def in_cluster(self, item, cluster):
        if (self.dist(item, cluster) - self.cluster_size[cluster] >= self.thres):
            return False
        else:
            for i in self.clusters[cluster]:
                if self.dist(item, i) < self.thres:
                    return True
            return False

    def process(self, items):
        for i in items:
            clust_iter = filter(lambda x: self.in_cluster(i, x), self.clusters.copy())
            cluster = next(clust_iter, None)
            if (cluster is not None):
                self.clusters[cluster].append(i)
                self.cluster_size[cluster] = max(self.cluster_size[cluster], self.dist(cluster, i))
                clust_merge = next(clust_iter, None)
                while(clust_merge is not None):
                    self.clusters[cluster] = self.clusters[cluster].union(self.clusters[clust_merge])
                    self.cluster_size[cluster] = functools.reduce(lambda x, y: max(x, self.dist(cluster, y), self.clusters[clust_merge], self.cluster_size[cluster]))
                    del self.clusters[clust_merge]
                    del self.cluster_size[clust_merge]
                    clust_merge = next(clust_iter, None)
            else:
                self.clusters[i] = {i}
                self.cluster_size[i] = 0


class ZoteroDocumentMerger(object):
    """Base class to handle document merging.  Consumers should iterate over interactive_merge.
       Implementors must override duplicates() to iterate over sets of duplicate documents"""

    def __init__(self, library):
        self._library = library
        self._merges = dict()
        self._to_merge = None
        self._cur_attr = None
        self._cur_item_type = None

    def attr_merge(self, attr):
        self._cur_attr = attr
        vals = [i[attr] for i in self._to_merge]
        if (hasattr(self, "merge_" + attr)):
            return getattr(self, "merge_" + attr)(vals)
        else:
            return self.default_attr_merge(vals)

    def merge_itemType(self, vals):
        counts = dict()
        for i in vals:
            counts[i] = counts.get(i, 0) + 1
        item_type = None
        for i in counts:
            if (counts[i] > counts.get(item_type, 0)):
                item_type = i
        return item_type

    def default_attr_merge(self, vals):
        val = None
        for v in vals:
            if ((val is None and v is not None) or (not val and v)):
                val = v
        return val

    def _merge_sets(self, vals):
        result = set()
        for v in vals:
            if (v is not None):
                result = result.union(v)
        return result

    def merge_children(self, vals):
        return self._merge_sets(vals)

    def merge_collections(self, vals):
        return self._merge_sets(vals)

    def merge_tags(self, vals):
        return self._merge_sets(vals)

    def merge_relations(self, vals):
        result = dict()
        for v in vals:
            if (v is not None):
                for rtype in v:
                    v_rtype_list = v[rtype] if isinstance(v[rtype], list) else [v[rtype]]
                    result[rtype] = result.get(rtype, []) + v_rtype_list
        return result

    def apply_merge(self, tuple, result):
        target = next(filter(lambda x: x.type == result['itemType'], tuple))
        for i in (i for i in tuple if i != target):
            i.delete()
        for pkey in result:
            target[pkey] = result[pkey]

    def interactive_merge(self):
        """Generator yields a tuple (tuple_of_docs_to_merge, proposed_merge) and expects either False or a dict
            specifying the result of the merger to be passed back."""
        self.build_merges()
        for tup in self._merges:
            result = yield (tup, self._merges[tup])
            if (result):
                self.apply_merge(tup, result)
        self._merges = dict()

    def duplicates(self):
        pass

    def build_merges(self):
        for dups in self.duplicates():
            self._to_merge = tuple(dups)
            merge = dict()
            self._cur_item_type = self.merge_itemType([i['itemType'] for i in self._to_merge])
            merge["itemType"] = self._cur_item_type
            for field in set(itertools.chain(self._library.item_fields[self._cur_item_type], self._library.special_fields)):
                merge[field] = self.attr_merge(field)
            self._merges[self._to_merge] = merge

    def merge_creators(self, vals):
        creators = [c for list in vals for c in list if c.type in self._library.item_creator_types[self._cur_item_type]]
        grouping = dict()

        def in_group(per, key):
            return next(filter(lambda x: per.same(x), grouping[key]), False)
        for p in (p.creator for p in creators):
            match_iter = filter(lambda y: in_group(p, y), grouping.copy())
            group = next(match_iter, False)
            if (group):
                grouping[group].add(p)
                merge_group = next(match_iter, False)
                while (merge_group):
                    grouping[group].update(grouping[merge_group])
                    del grouping[merge_group]
            else:
                grouping[p] = {p}
        mapping = dict()
        for key in grouping:
            merge_person = Person.merge(*(grouping[key]))
            for i in grouping[key]:
                mapping[i] = merge_person
        used = set()
        result = []
        for c in creators:
            person = mapping[c.creator]
            type = c.type
            if ((person, type) not in used):
                used.add((person, type))
                result.append(Creator.factory(person.firstname, person.lastname, type))
        return result


class SimpleZDocMerger(ZoteroDocumentMerger):
    """Merges documents based on having the same title string ignoring case and punctuation"""

    def __init__(self, library):
        super().__init__(library)
        self._buckets = dict()
        self.find_duplicates()

    @staticmethod
    def build_name_key(string):
        return re.sub('\W', '', string.casefold())

    def find_duplicates(self):
        for i in self._library.documents:
            namekey = self.build_name_key(i.title)
            if (len(namekey) > 3):
                if namekey not in self._buckets:
                    self._buckets[namekey] = set()
                self._buckets[namekey].add(i)

    def duplicates(self):
        yield from self._buckets.values()
