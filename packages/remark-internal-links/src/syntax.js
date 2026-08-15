import { codes } from 'micromark-util-symbol';

export function syntax() {
    const aliasDivider = '|'.charCodeAt(0);

    function tokenize(effects, ok, nok) {
        function start(code) {
            effects.enter('internalLink');
            effects.enter('internalLinkMarker');
            effects.consume(code);
            return open;
        }
        function open(code) {
            if (code !== codes.leftSquareBracket) return nok(code);
            effects.consume(code);
            effects.exit('internalLinkMarker');
            effects.enter('internalLinkTarget');
            return target;
        }
        function target(code) {
            if (code === aliasDivider) {
                effects.exit('internalLinkTarget');
                effects.enter('internalLinkAliasDivider');
                effects.consume(code);
                effects.exit('internalLinkAliasDivider');
                effects.enter('internalLinkAlias');
                return alias;
            }
            if (code === codes.rightSquareBracket) {
                effects.exit('internalLinkTarget');
                effects.enter('internalLinkMarker');
                effects.consume(code);
                return close;
            }
            if (code === codes.eof || code === codes.lineFeed) return nok(code);
            effects.consume(code);
            return target;
        }
        function alias(code) {
            if (code === codes.rightSquareBracket) {
                effects.exit('internalLinkAlias');
                effects.enter('internalLinkMarker');
                effects.consume(code);
                return close;
            }
            if (code === codes.eof || code === codes.lineFeed || code === aliasDivider) return nok(code);
            effects.consume(code);
            return alias;
        }
        function close(code) {
            if (code !== codes.rightSquareBracket) return nok(code);
            effects.consume(code);
            effects.exit('internalLinkMarker');
            effects.exit('internalLink');
            return ok;
        }
        return start;
    }

    return {
        text: { [codes.leftSquareBracket]: { tokenize } },
    };
}
