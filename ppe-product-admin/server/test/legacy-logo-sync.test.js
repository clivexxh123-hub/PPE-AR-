const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const {
    collectLegacyLogos,
    parseLegacyLogoFilename,
    repairLegacyText
} = require("../scripts/sync-legacy-logos");

test("repairs legacy UTF-8 filenames that were decoded as latin1", () => {
    const corrupted = Buffer.from("国家电网-北京", "utf8").toString("latin1");
    assert.equal(repairLegacyText(corrupted), "国家电网-北京");
});

test("maps a legacy logo filename to the new ai_logo_assets fields", () => {
    const corrupted = Buffer.from("国家电网-北京", "utf8").toString("latin1");
    const parsed = parseLegacyLogoFilename(`1786440518049-${corrupted}.png`);
    assert.deepEqual(
        {
            companyName: parsed.companyName,
            region: parsed.region,
            logoKey: parsed.logoKey,
            logoName: parsed.logoName,
            logoUrl: parsed.logoUrl
        },
        {
            companyName: "国家电网",
            region: "北京",
            logoKey: "北京-国家电网",
            logoName: "国家电网-北京.png",
            logoUrl: "/uploads/logos/1786440518049-国家电网-北京.png"
        }
    );
});

test("discovers the four unique legacy logo materials", () => {
    const directory = path.resolve(__dirname, "..", "uploads", "logos");
    const logos = collectLegacyLogos(directory);
    assert.equal(logos.length, 4);
    assert.deepEqual(
        logos.map(item => item.companyName).sort((a, b) => a.localeCompare(b, "zh-CN")),
        ["保利集团", "东方电气集团", "国家电投", "国家电网"].sort((a, b) => a.localeCompare(b, "zh-CN"))
    );
});
