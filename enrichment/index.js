import express from "express";
import { readFileSync } from "node:fs";

const app = express();
const port = Number(process.env.PORT || 3232);
const maxInputLength = 100_000;
const rawEnrichBodyParser = express.raw({ type: () => true, limit: "128kb" });

const combinedLaws = JSON.parse(
    readFileSync(new URL("./zh/src/laws_combined.json", import.meta.url), "utf8")
);

const federalLanguagePreference = ["fr", "de", "it", "en"];
const officialLawsByAbbreviation = buildOfficialLawsByAbbreviation(combinedLaws);

// Regex for article and paragraph references in DE, FR and IT.
const citationMarkerPattern = String.raw`§+|Art|art|Artikel|article|Article|articolo|Articolo|Paragraph|Par|par`;
const provisionPattern = String.raw`\d+(?:[a-zA-Z]\b)?`;
const citationRangePattern = String.raw`(?:\s*(?:-|–|—|bis|à|a)\s*${provisionPattern})?`;
const citationDetailPattern =
    citationRangePattern +
    String.raw`(?:\s*(?:Abs|Absatz|Al|al|Cpv|cpv)\.?\s*${provisionPattern})?` +
    String.raw`(?:\s*(?:Ziff|Ziffer|Ch|ch|N|n)\.?\s*${provisionPattern})?` +
    String.raw`(?:\s*(?:Lit|lit|Buchstabe|Bchst|Let|let|Lett|lett)\.?\s*[A-Za-z])?` +
    String.raw`(?:\s*f{1,2}\.)?`;
const lawAbbreviationTokenCharacter = String.raw`[\p{L}\p{N}/+–().-]`;
const lawAbbreviationFinalCharacter = String.raw`[\p{L}\p{N})/+–-]`;
const lawAbbreviationToken = String.raw`(?:\(?[\p{Lu}\p{N}](?:${lawAbbreviationTokenCharacter}*${lawAbbreviationFinalCharacter})?|[\p{Ll}]+(?:[\p{Lu}\p{N}/+–().-])(?:${lawAbbreviationTokenCharacter}*${lawAbbreviationFinalCharacter})?)`;
const combinationConnectorPattern = String.raw`(?:,|;|/|&|\b(?:und|sowie|oder|beziehungsweise|respektive|wie\s+auch|et|ou|ainsi\s+que|de\s+même\s+que|soit|voire|e|ed|o|od|oppure|nonché|nonche|rispettivamente|ossia|ovvero)\b|\b(?:bzw|resp)\.|\bi\.?\s*V\.?\s*m\.?)`;
const combinationSeparatorPattern = String.raw`\s*${combinationConnectorPattern}\s*`;
const regexCitationStart = new RegExp(
    String.raw`(?<![\p{L}\p{N}_])(?<citation>(?<marker>${citationMarkerPattern})\.?\s*(?<provision>${provisionPattern})${citationDetailPattern})`,
    "gu"
);
const regexConnectedCitationChunk = new RegExp(
    String.raw`(?<separator>${combinationSeparatorPattern})(?<citation>(?:(?:${citationMarkerPattern})\.?\s*)?(?<provision>${provisionPattern})${citationDetailPattern})`,
    "iuy"
);
const regexLawAbbreviationToken = new RegExp(lawAbbreviationToken, "uy");
const regexTrailingBlockedUnit = /^\s*(?:%|prozent|percent|pourcent|per\s+cento|promille|franken|chf|euro|eur|jahre|jahr|monate|monat|tage|tag|stunden|stunde|personen|person|einwohner|einwohnerinnen|habitants|persone)\b/iu;

//Regex for BGE/ATF/DTF (DE/FR/IT)
const regexBGE = /(?:(?:(BGE|ATF|DTF)\.?\s*)?(\d+(?:\w\b)?)\s*M{0,4}(IV|V|I{1,3}[ab]?)+\s*(\d+(?:\w\b)?))/gi

//Regex for BGer reference Number (Geschäftsnr./Num. référence/N. riferimento)
const regexBGer = /(\d+)([A-Z])_(\d+\/\d+)/g

function enrichMarkdown(text, options = {}) {
    text = enrichLawReferences(text, options.defaultLaw);

    // Highlight reference Numbers
    text = text.replace(regexBGer, function (ref) {
        // let response = [...ref.matchAll(regexBGer)]; //if array of matches needed
        return buildMarkdownLink(ref, "https://links.weblaw.ch/" + encodeURIComponent(ref)); //Todo convert link to admin.ch link
    });

    //Highlight BGEs with <a>...</a>
    return text.replace(regexBGE, function (ref) {
        let res = [...ref.matchAll(regexBGE)];
        let lang;

        if (!res[0][1]) {
            res[0][1] = "BGE";
        }
        if (res[0][1] == "BGE") {
            lang = "de";
        }
        if (res[0][1] == "ATF") {
            lang = "fr";
        }
        if (res[0][1] == "DTF") {
            lang = "it";
        }
        let link = "https://www.bger.ch/ext/eurospider/live/" + lang + "/php/aza/http/index.php?lang=" + lang + "&type=show_document&page=1&from_date=&to_date=&sort=relevance&insertion_date=&top_subcollection_aza=all&query_words=&rank=0&azaclir=aza&highlight_docid=atf%3A%2F%2F" + res[0][2] + "-" + res[0][3] + "-" + res[0][4] + "%3A" + lang + "&number_of_ranks=0#page" + res[0][4];
        return buildMarkdownLink(ref, link);
    })
};

function buildOfficialLawsByAbbreviation(lawData) {
    const lawsByAbbreviation = new Map();

    addZurichLaws(lawsByAbbreviation, lawData.zh || []);
    addFederalLaws(lawsByAbbreviation, lawData.ch || []);

    return lawsByAbbreviation;
}

function addZurichLaws(lawsByAbbreviation, laws) {
    for (const law of laws) {
        const abbreviation = normalizeLawAbbreviation(law.law_title_abbreviation);

        if (!abbreviation || !law.in_force || !law.dynamic_prod_url) {
            continue;
        }

        lawsByAbbreviation.set(abbreviation, {
            abbreviation,
            dynamic_prod_url: law.dynamic_prod_url,
            dynamic_source_url: law.dynamic_source_url,
            language: null,
            law,
            scope: "zh",
        });
    }
}

function addFederalLaws(lawsByAbbreviation, laws) {
    for (const law of laws) {
        if (!law.in_force || !law.law_title_abbreviation || !law.dynamic_prod_url) {
            continue;
        }

        for (const lawEntry of getFederalLawEntries(law)) {
            for (const abbreviation of getLawAbbreviationAliases(lawEntry.abbreviation)) {
                if (!lawsByAbbreviation.has(abbreviation)) {
                    lawsByAbbreviation.set(abbreviation, lawEntry);
                }
            }
        }
    }
}

function getFederalLawEntries(law) {
    const entriesByAbbreviation = new Map();

    for (const language of federalLanguagePreference) {
        const abbreviation = normalizeLawAbbreviation(law.law_title_abbreviation[language]);
        const dynamicProdUrl = law.dynamic_prod_url[language];
        const dynamicSourceUrl = law.dynamic_source_url?.[language];

        if (!abbreviation || !dynamicProdUrl || !dynamicSourceUrl || entriesByAbbreviation.has(abbreviation)) {
            continue;
        }

        entriesByAbbreviation.set(abbreviation, {
            abbreviation,
            dynamic_prod_url: dynamicProdUrl,
            dynamic_source_url: dynamicSourceUrl,
            language,
            law,
            scope: "ch",
        });
    }

    return entriesByAbbreviation.values();
}

function getLawAbbreviationAliases(abbreviation) {
    const aliases = new Set([abbreviation]);
    const abbreviationWithoutTrailingDots = abbreviation.replace(/\.+$/u, "");

    if (abbreviationWithoutTrailingDots) {
        aliases.add(abbreviationWithoutTrailingDots);
    }

    return aliases;
}

function enrichLawReferences(text, defaultLaw) {
    let enrichedText = "";
    let cursor = 0;

    regexCitationStart.lastIndex = 0;

    for (let match = regexCitationStart.exec(text); match; match = regexCitationStart.exec(text)) {
        if (match.index < cursor) {
            continue;
        }

        const reference = parseLawReference(text, match, defaultLaw);

        if (!reference) {
            continue;
        }

        enrichedText += text.slice(cursor, match.index) + renderLawReference(reference, text);
        cursor = reference.endIndex;
        regexCitationStart.lastIndex = reference.endIndex;
    }

    return enrichedText + text.slice(cursor);
}

function parseLawReference(text, startMatch, defaultLaw) {
    const chunks = [{
        startIndex: startMatch.index,
        endIndex: startMatch.index + startMatch[0].length,
        label: startMatch.groups.citation,
        provision: startMatch.groups.provision,
    }];
    let endIndex = chunks[0].endIndex;

    for (;;) {
        regexConnectedCitationChunk.lastIndex = endIndex;
        const chunkMatch = regexConnectedCitationChunk.exec(text);

        if (!chunkMatch) {
            break;
        }

        const chunkStartIndex = chunkMatch.index + chunkMatch.groups.separator.length;

        chunks.push({
            startIndex: chunkStartIndex,
            endIndex: chunkMatch.index + chunkMatch[0].length,
            label: chunkMatch.groups.citation,
            provision: chunkMatch.groups.provision,
        });
        endIndex = chunkMatch.index + chunkMatch[0].length;
    }

    const trailingLaw = findTrailingLaw(text, endIndex);

    if (trailingLaw?.law) {
        return {
            chunks,
            law: trailingLaw.law,
            endIndex: trailingLaw.endIndex,
        };
    }

    if (trailingLaw?.unknownAbbreviation) {
        return {
            chunks: [],
            law: null,
            markdown: text.slice(startMatch.index, trailingLaw.endIndex),
            endIndex: trailingLaw.endIndex,
        };
    }

    if (!defaultLaw || hasUnsafeTrailingUnit(text, endIndex)) {
        return null;
    }

    return {
        chunks,
        law: defaultLaw,
        endIndex,
    };
}

function findTrailingLaw(text, index) {
    const whitespaceMatch = /^\s+/.exec(text.slice(index));

    if (!whitespaceMatch) {
        return null;
    }

    const firstTokenIndex = index + whitespaceMatch[0].length;
    const candidates = [];
    let tokenStartIndex = firstTokenIndex;
    let tokenEndIndex = firstTokenIndex;

    for (let tokenCount = 0; tokenCount < 4; tokenCount += 1) {
        regexLawAbbreviationToken.lastIndex = tokenStartIndex;
        const tokenMatch = regexLawAbbreviationToken.exec(text);

        if (!tokenMatch) {
            break;
        }

        tokenEndIndex = tokenStartIndex + tokenMatch[0].length;
        candidates.push({
            abbreviation: text.slice(firstTokenIndex, tokenEndIndex),
            endIndex: tokenEndIndex,
        });

        const nextWhitespaceMatch = /^\s+/.exec(text.slice(tokenEndIndex));

        if (!nextWhitespaceMatch) {
            break;
        }

        tokenStartIndex = tokenEndIndex + nextWhitespaceMatch[0].length;
    }

    if (candidates.length === 0) {
        return null;
    }

    for (const candidate of candidates.toReversed()) {
        const law = officialLawsByAbbreviation.get(normalizeLawAbbreviation(candidate.abbreviation));

        if (law) {
            return {
                law,
                abbreviation: candidate.abbreviation,
                endIndex: candidate.endIndex,
            };
        }
    }

    return {
        unknownAbbreviation: candidates[0].abbreviation,
        endIndex: candidates[0].endIndex,
    };
}

function hasUnsafeTrailingUnit(text, index) {
    return regexTrailingBlockedUnit.test(text.slice(index));
}

function renderLawReference(reference, sourceText) {
    if (reference.markdown) {
        return reference.markdown;
    }

    let markdown = "";
    let cursor = reference.chunks[0].startIndex;

    for (const chunk of reference.chunks) {
        markdown += sourceText.slice(cursor, chunk.startIndex);
        markdown += buildMarkdownLink(chunk.label, buildProvisionUrl(reference.law, chunk.provision));
        cursor = chunk.endIndex;
    }

    markdown += sourceText.slice(cursor, reference.endIndex);
    return markdown;
}

function buildOdatProvisionUrl(law, provision) {
    return law.dynamic_prod_url + "-latest.html#seq-0-prov-" + encodeURIComponent(provision.toLowerCase());
}

function buildProvisionUrl(law, provision) {
    if (law.scope === "ch") {
        return buildFedlexProvisionUrl(law, provision);
    }

    return buildOdatProvisionUrl(law, provision);
}

function buildFedlexProvisionUrl(law, provision) {
    return law.dynamic_source_url + "#art_" + encodeURIComponent(provision.toLowerCase());
}

function normalizeLawAbbreviation(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
}

function buildMarkdownLink(label, url) {
    return "[" + escapeMarkdownLinkLabel(label) + "](" + encodeMarkdownLinkDestination(url) + ")";
}

function escapeMarkdownLinkLabel(value) {
    return String(value).replace(/([\\\[\]])/g, "\\$1");
}

function encodeMarkdownLinkDestination(value) {
    return String(value)
        .replaceAll(" ", "%20")
        .replaceAll("(", "%28")
        .replaceAll(")", "%29");
}

function parseSanitizedJsonBody(rawBody) {
    return JSON.parse(sanitizeJsonInput(rawBody));
}

function getRawRequestBody(request) {
    if (Buffer.isBuffer(request.body)) {
        return request.body.toString("utf8");
    }

    return String(request.body || "{}");
}

function sanitizeJsonInput(rawBody) {
    const body = String(rawBody);
    let sanitizedBody = "";
    let index = body.charCodeAt(0) === 0xFEFF ? 1 : 0;

    while (index < body.length) {
        const character = body[index];

        if (character !== '"') {
            sanitizedBody += sanitizeJsonStructuralCharacter(character);
            index += 1;
            continue;
        }

        const jsonString = readJsonLikeString(body, index + 1);
        sanitizedBody += '"' + sanitizeJsonString(jsonString.value) + '"';
        index = jsonString.endIndex + 1;
    }

    return sanitizedBody;
}

function sanitizeJsonString(value) {
    return String(value)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\n/g, "\\n")
        .replace(/\r/g, "\\r")
        .replace(/\t/g, "\\t")
        .replace(/[\u0000-\u001F\u007F-\u009F]/g, "");
}

function readJsonLikeString(body, startIndex) {
    let value = "";
    let index = startIndex;

    while (index < body.length) {
        const character = body[index];

        if (character === '"' && isJsonStringClosingQuote(body, index)) {
            return { value, endIndex: index };
        }

        if (character === "\\" && index + 1 < body.length) {
            const decodedEscape = decodeJsonEscape(body, index);

            if (decodedEscape) {
                value += decodedEscape.value;
                index = decodedEscape.endIndex + 1;
                continue;
            }
        }

        value += character;
        index += 1;
    }

    return { value, endIndex: body.length };
}

function isJsonStringClosingQuote(body, quoteIndex) {
    const nextSyntaxCharacter = body.slice(quoteIndex + 1).match(/\S/u)?.[0];
    return !nextSyntaxCharacter || nextSyntaxCharacter === ":" || nextSyntaxCharacter === "," || nextSyntaxCharacter === "}" || nextSyntaxCharacter === "]";
}

function decodeJsonEscape(body, backslashIndex) {
    const escapeCharacter = body[backslashIndex + 1];

    if (escapeCharacter === '"' || escapeCharacter === "\\" || escapeCharacter === "/") {
        return { value: escapeCharacter, endIndex: backslashIndex + 1 };
    }

    if (escapeCharacter === "b") {
        return { value: "\b", endIndex: backslashIndex + 1 };
    }

    if (escapeCharacter === "f") {
        return { value: "\f", endIndex: backslashIndex + 1 };
    }

    if (escapeCharacter === "n") {
        return { value: "\n", endIndex: backslashIndex + 1 };
    }

    if (escapeCharacter === "r") {
        return { value: "\r", endIndex: backslashIndex + 1 };
    }

    if (escapeCharacter === "t") {
        return { value: "\t", endIndex: backslashIndex + 1 };
    }

    if (escapeCharacter === "u") {
        const hex = body.slice(backslashIndex + 2, backslashIndex + 6);

        if (/^[0-9a-f]{4}$/iu.test(hex)) {
            return { value: String.fromCharCode(Number.parseInt(hex, 16)), endIndex: backslashIndex + 5 };
        }
    }

    return null;
}

function sanitizeJsonStructuralCharacter(character) {
    if (character === "\t" || character === "\n" || character === "\r") {
        return character;
    }

    if (character.charCodeAt(0) < 0x20) {
        return " ";
    }

    return character;
}

app.disable("x-powered-by");

app.get("/health", (request, response) => {
    response.json({ status: "ok" });
});

app.post("/enrich", rawEnrichBodyParser, (request, response) => {
    let body;

    try {
        body = parseSanitizedJsonBody(getRawRequestBody(request));
    } catch {
        response.status(400).json({ error: "Request body must be valid JSON." });
        return;
    }

    const { text } = body || {};
    const defaultLawInput = body?.["default-law"];

    if (typeof text !== "string") {
        response.status(400).json({ error: "Request body must include a string field named text." });
        return;
    }

    if (text.length > maxInputLength) {
        response.status(413).json({ error: "Text exceeds the maximum allowed length." });
        return;
    }

    if (defaultLawInput !== undefined && typeof defaultLawInput !== "string") {
        response.status(400).json({ error: "Optional default-law field must be a string." });
        return;
    }

    const defaultLaw = defaultLawInput
        ? officialLawsByAbbreviation.get(normalizeLawAbbreviation(defaultLawInput))
        : null;

    if (defaultLawInput && !defaultLaw) {
        response.status(400).json({ error: "default-law must match a known official law abbreviation." });
        return;
    }

    response.json({ markdown: enrichMarkdown(text, { defaultLaw }) });
});

app.use((error, request, response, next) => {
    if (error?.type === "entity.too.large") {
        response.status(413).json({ error: "Request body exceeds the maximum allowed size." });
        return;
    }

    if (error instanceof SyntaxError && error.status === 400 && "body" in error) {
        response.status(400).json({ error: "Request body must be valid JSON." });
        return;
    }

    next(error);
});

app.listen(port, "0.0.0.0", () => {
    console.log(`enrichment dev server listening on ${port}`);
});
