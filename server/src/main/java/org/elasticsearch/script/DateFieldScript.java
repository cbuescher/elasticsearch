/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the Elastic License
 * 2.0 and the Server Side Public License, v 1; you may not use this file except
 * in compliance with, at your election, the Elastic License 2.0 or the Server
 * Side Public License, v 1.
 */

package org.elasticsearch.script;

import org.apache.lucene.index.LeafReaderContext;
import org.elasticsearch.common.time.DateFormatter;
import org.elasticsearch.search.lookup.SearchLookup;

import java.util.Map;
import java.util.Objects;
import java.util.function.Function;

public abstract class DateFieldScript extends AbstractLongFieldScript {
    public static final ScriptContext<Factory> CONTEXT = newContext("date_field", Factory.class);

    public static final Factory PARSE_FROM_SOURCE = new Factory() {
        @Override
        public LeafFactory newFactory(
            String field,
            Map<String, Object> params,
            SearchLookup lookup,
            DateFormatter formatter,
            boolean onErrorContinue
        ) {
            return ctx -> new DateFieldScript(field, params, lookup, formatter, ctx, false) {
                @Override
                public void execute() {
                    emitFromSource();
                }
            };
        }

        @Override
        public boolean isResultDeterministic() {
            return true;
        }
    };

    public static Factory leafAdapter(Function<SearchLookup, CompositeFieldScript.LeafFactory> parentFactory) {
        return (leafFieldName, params, searchLookup, formatter, onErrorContinue) -> {
            CompositeFieldScript.LeafFactory parentLeafFactory = parentFactory.apply(searchLookup);
            return (LeafFactory) ctx -> {
                CompositeFieldScript compositeFieldScript = parentLeafFactory.newInstance(ctx);
                return new DateFieldScript(leafFieldName, params, searchLookup, formatter, ctx, false) {
                    @Override
                    public void setDocument(int docId) {
                        compositeFieldScript.setDocument(docId);
                    }

                    @Override
                    public void execute() {
                        emitFromCompositeScript(compositeFieldScript);
                    }
                };
            };
        };
    }

    @SuppressWarnings("unused")
    public static final String[] PARAMETERS = {};

    public interface Factory extends ScriptFactory {
        LeafFactory newFactory(
            String fieldName,
            Map<String, Object> params,
            SearchLookup searchLookup,
            DateFormatter formatter,
            boolean onErrorContinue
        );
    }

    public interface LeafFactory {
        DateFieldScript newInstance(LeafReaderContext ctx);
    }

    private final DateFormatter formatter;

    public DateFieldScript(
        String fieldName,
        Map<String, Object> params,
        SearchLookup searchLookup,
        DateFormatter formatter,
        LeafReaderContext ctx,
        boolean onErrorContinue
    ) {
        super(fieldName, params, searchLookup, ctx, onErrorContinue);
        this.formatter = formatter;
    }

    @Override
    protected void emitFromObject(Object v) {
        try {
            emit(formatter.parseMillis(Objects.toString(v)));
        } catch (Exception e) {
            // ignore
        }
    }

    public static class Emit {
        private final DateFieldScript script;

        public Emit(DateFieldScript script) {
            this.script = script;
        }

        public void emit(long v) {
            script.checkMaxSize(script.count());
            script.emit(v);
        }
    }

    /**
     * Temporary parse method that takes into account the date format. We'll
     * remove this when we have "native" source parsing fields.
     */
    public static class Parse {
        private final DateFieldScript script;

        public Parse(DateFieldScript script) {
            this.script = script;
        }

        public long parse(Object str) {
            return script.formatter.parseMillis(str.toString());
        }
    }
}
