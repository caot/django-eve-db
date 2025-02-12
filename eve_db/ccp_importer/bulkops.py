# Bulk insert/update DB operations for the Django ORM. Useful when
# inserting/updating lots of objects where the bottleneck is overhead
# in talking to the database. Instead of doing this
#
#   for x in seq:
#       o = SomeObject()
#       o.foo = x
#       o.save()
#
# or equivalently this
#
#   for x in seq:
#       SomeObject.objects.create(foo=x)
#
# do this
#
#   l = []
#   for x in seq:
#       o = SomeObject()
#       o.foo = x
#       l.append(o)
#   insert_many(l)
#
# Note that these operations are really simple. They won't work with
# many-to-many relationships, and you may have to divide really big
# lists into smaller chunks before sending them through.
#
# How to use:
#
# if bulk_save:
#    for _k, v in to_class_name_objs_dict(obj_list_update).items():
#        update_many(v)
#
#    for _k, v in to_class_name_objs_dict(obj_list_insert).items():
#        insert_many(v)

def chunks(data=[], n=500):
    """Yield successive n-sized chunks from data list."""
    for i in range(0, len(data), n):
        yield data[i:i + n]

def to_class_name_objs_dict(objs=[]):
    data = OrderedDict()

    for x in objs:
        k = x.__class__.__name__
        v = data.get(k, [])
        v.append(x)

        data.update({k: v})

    return data

def insert_many(objects, using="default"):
    """Insert list of Django objects in one SQL query. Objects must be
    of the same Django model. Note that save is not called and signals
    on the model are not raised."""
    if not objects:
        return

    import django.db.models
    from django.db import connections
    con = connections[using]
    
    model = objects[0].__class__
    fields = [f for f in model._meta.fields if not isinstance(f, django.db.models.AutoField)]
    parameters = []
    for o in objects:
        parameters.append(tuple(f.get_db_prep_save(f.pre_save(o, True), connection=con) for f in fields))
    table = model._meta.db_table
    column_names = ",".join(con.ops.quote_name(f.column) for f in fields)
    placeholders = ",".join(("%s",) * len(fields))
    con.cursor().executemany(
        "insert into %s (%s) values (%s)" % (table, column_names, placeholders),
        parameters)

def update_many(objects, fields=[], using="default"):
    """Update list of Django objects in one SQL query, optionally only
    overwrite the given fields (as names, e.g. fields=["foo"]).
    Objects must be of the same Django model. Note that save is not
    called and signals on the model are not raised."""
    if not objects:
        return

    import django.db.models
    from django.db import connections
    con = connections[using]

    names = fields
    meta = objects[0]._meta
    fields = [f for f in meta.fields if not isinstance(f, django.db.models.AutoField) and (not names or f.name in names)]

    if not fields:
        raise ValueError("No fields to update, field names are %s." % names)
    
    fields_with_pk = fields + [meta.pk]
    parameters = []
    for o in objects:
        parameters.append(tuple(f.get_db_prep_save(f.pre_save(o, True), connection=con) for f in fields_with_pk))

    table = meta.db_table
    assignments = ",".join(("%s=%%s"% con.ops.quote_name(f.column)) for f in fields)
    con.cursor().executemany(
        "update %s set %s where %s=%%s" % (table, assignments, meta.pk.column),
        parameters)
