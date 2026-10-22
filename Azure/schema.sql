DROP TABLE IF EXISTS AbilityRank;
DROP TABLE IF EXISTS Ability;
DROP TABLE IF EXISTS Champion_Tag;
DROP TABLE IF EXISTS Patch_Champion;
DROP TABLE IF EXISTS Skin;
DROP TABLE IF EXISTS Tag;
DROP TABLE IF EXISTS Rarity;
DROP TABLE IF EXISTS SkinLine;
DROP TABLE IF EXISTS Champion;
DROP TABLE IF EXISTS Patch;

--Patch
CREATE TABLE Patch (
    PatchID VARCHAR(30) PRIMARY KEY,
);

--Champion
CREATE TABLE Champion (
    ChampionID INT PRIMARY KEY,
    Name VARCHAR(50) NOT NULL,
    InternalName VARCHAR(50) NOT NULL,
    Title VARCHAR(100) NOT NULL,
    Blurb VARCHAR(400) NOT NULL,
    Partype VARCHAR(20) NOT NULL
);

--Mage, Fighter etc
CREATE TABLE Tag (
    TagName VARCHAR(20) PRIMARY KEY
);

CREATE TABLE Champion_Tag (
    ChampionID INT NOT NULL REFERENCES Champion(ChampionID),
    TagID VARCHAR(20) NOT NULL REFERENCES Tag(TagName),
    PRIMARY KEY (ChampionID, TagID)
);

--Patch_Champion stats

CREATE TABLE Patch_Champion (
    PatchID VARCHAR(30) NOT NULL REFERENCES Patch(PatchID),
    ChampionID INT NOT NULL REFERENCES Champion(ChampionID),
    PRIMARY KEY (PatchID, ChampionID),

    --info
    Attack TINYINT NOT NULL,
    Defense TINYINT NOT NULL,
    Magic TINYINT NOT NULL,
    Difficulty TINYINT NOT NULL,

    --stats
    Hp FLOAT NOT NULL,
    Hpperlevel FLOAT NOT NULL,
    Mp FLOAT NOT NULL,
    Mpperlevel FLOAT NOT NULL,
    Movespeed FLOAT NOT NULL,
    Armor FLOAT NOT NULL,
    Armorperlevel FLOAT NOT NULL,
    Spellblock FLOAT NOT NULL,
    Spellblockperlevel FLOAT NOT NULL,
    Attackrange FLOAT NOT NULL,
    Hpregen FLOAT NOT NULL,
    Hpregenperlevel FLOAT NOT NULL,
    Mpregen FLOAT NOT NULL,
    Mpregenperlevel FLOAT NOT NULL,
    Crit FLOAT NOT NULL,
    Critperlevel FLOAT NOT NULL,
    Attackdamage FLOAT NOT NULL,
    Attackdamageperlevel FLOAT NOT NULL,
    Attackspeedperlevel FLOAT NOT NULL,
    Attackspeed FLOAT NOT NULL
);
--Champion Abilities

CREATE TABLE Ability (
    AbilityID INT IDENTITY(1,1) PRIMARY KEY,
    Type TINYINT CHECK (Type IN (1,2,3,4,5)) NOT NULL,
    ChampionID INT NOT NULL REFERENCES Champion(ChampionID),
    Name VARCHAR(50) NOT NULL UNIQUE,
    Description VARCHAR(1000) UNIQUE,
    UNIQUE (Type, ChampionID)

);

CREATE TABLE AbilityRank(
    AbilityID INT NOT NULL REFERENCES Ability(AbilityID),
    Rank TINYINT NOT NULL,
    PatchID VARCHAR(30) REFERENCES Patch(PatchID),
    PRIMARY KEY (AbilityID, Rank),
    Cooldown DECIMAL (6,2) NOT NULL
);

--Skin
CREATE TABLE SkinLine (
    SkinLineID INT PRIMARY KEY,
    Name VARCHAR(50),
    Lore VARCHAR(1000)
);

CREATE TABLE Rarity (
    RarityID INT IDENTITY(1,1) PRIMARY KEY,
    Name VARCHAR(50) NOT NULL CHECK (Name IN ('Transcendent', 'Exalted', 'Ultimate', 'Mythic', 'Prestige', 'Legendary', 'Epic', 'Rare', 'Common')) UNIQUE,
    PriceRP INT,
    PriceBE INT
);

CREATE TABLE Skin (
    SkinID INT PRIMARY KEY,
    ChampionID INT NOT NULL REFERENCES Champion(ChampionID),
    SkinLineID INT REFERENCES SkinLine(SkinLineID),
    Number SMALLINT NOT NULL,
    Name VARCHAR(50) NOT NULL,
    isLegacy BIT NOT NULL,
    RarityID INT REFERENCES Rarity(RarityID),
    UNIQUE (ChampionID, Number)
);

SELECT COUNT(*) FROM Champion_Tag;
SELECT * FROM Tag;
SELECT * FROM Champion_Tag;
SELECT * FROM Champion;
SELECT * FROM Patch_Champion;
DELETE FROM Patch_Champion;


-- first query

SELECT pc.PatchId, c.Name, pc.Hp, pc.Mp
FROM Champion c JOIN Patch_Champion pc ON c.ChampionID = pc.ChampionID
where c.Name = 'Xerath';

