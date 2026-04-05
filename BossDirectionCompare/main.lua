local mod = RegisterMod("Boss Direction Compare", 1)
local json = require("json")

------------------------------
-- 配置
------------------------------
local Stages = {
    '1','1a','1b','1c','1d',
    '2','2a','2b','2c','2d',
    '3','3a','3b','3c','3d',
    '4','4a','4b','4c','4d',
    '5','5a','5b','5c','5d',
    '6','6a','6b','6c','6d',
    '7','7a','7b','7c',
    '8','8a','8b','8c',
    -- '9',
    '10','10a',
    '11','11a',
    '12',
    -- '13','13a'
}

local TestItems = {
    { id = 102, type = "trinket",     name = "塔罗牌残片" },
    { id = 589, type = "collectible", name = "月亮" },
    { id = 599, type = "collectible", name = "巫毒娃娃的头" },
    { id = 626, type = "collectible", name = "刀把" },
}

------------------------------
-- 道具判断函数
------------------------------
function mod:HasCollectible(itemId)
    return Isaac.GetPlayer(0):GetCollectibleNum(itemId) > 0
end

function mod:HasTrinket(itemId)
    return Isaac.GetPlayer(0):GetTrinketMultiplier(itemId) > 0
end

function mod:HasItem(item)
    if item.type == "collectible" then
        return self:HasCollectible(item.id)
    elseif item.type == "trinket" then
        return self:HasTrinket(item.id)
    end
    return false
end

------------------------------
-- 获取头目房位置
------------------------------
function mod:GetBossPosition()
    local level = Game():GetLevel()
    local stage = level:GetStage()
    if stage == LevelStage.STAGE4_3 or stage == LevelStage.STAGE8 then
        return nil
    end
    local rooms = level:GetRooms()
    if stage ~= LevelStage.STAGE7 then
        return rooms:Get(level:GetLastBossRoomListIndex()).SafeGridIndex
    else -- The Void
        for i = 1, #rooms do
            local roomDesc = rooms:Get(i - 1)
            if roomDesc.Data and roomDesc.Data.Name == 'Delirium' then
                return roomDesc.SafeGridIndex
            end
        end
    end
    return nil
end

------------------------------
-- 存档读写
------------------------------
local data = {}
function mod:Save()
    mod:SaveData(json.encode(data))
end
function mod:Load()
    if mod:HasData() then
        data = json.decode(mod:LoadData()) or data
    end
end
function BDCResetData()
    data = {}
    mod:Save()
end

------------------------------
-- 对比并记录差异
------------------------------
function mod:CompareAndRecord()
    local state = data.state
    local baseline = state.bossPositions["0"]
    data.records = data.records or {}

    for i, item in ipairs(TestItems) do
        local phaseData = state.bossPositions[tostring(i)]
        local diffStages = {}
        for _, stageKey in ipairs(Stages) do
            local basePos = baseline[stageKey]
            local itemPos = phaseData[stageKey]
            if basePos ~= itemPos then
                table.insert(diffStages, {
                    stage = stageKey,
                    baseline = basePos,
                    withItem = itemPos,
                })
            end
        end
        table.insert(data.records, {
            seed = state.seed,
            item_id = item.id,
            item_type = item.type,
            item_name = item.name,
            diff_stages = diffStages,
            diff_count = #diffStages,
        })
    end
end

------------------------------
-- 控制台输出记录
------------------------------
function BDCShowRecords()
    if not data.records or #data.records == 0 then
        Isaac.ConsoleOutput("暂无测试记录\n")
        return
    end
    for i, record in ipairs(data.records) do
        if record.diff_count > 0 then
            local stageList = {}
            for _, diff in ipairs(record.diff_stages) do
                table.insert(stageList, diff.stage)
            end
            Isaac.ConsoleOutput(string.format(
                "#%d [%s] %s(%d): 差异楼层=%s\n",
                i, record.seed, record.item_name, record.item_id,
                table.concat(stageList, ",")))
        else
            Isaac.ConsoleOutput(string.format(
                "#%d [%s] %s(%d): 无差异\n",
                i, record.seed, record.item_name, record.item_id))
        end
    end
    Isaac.ConsoleOutput(string.format("共 %d 条记录\n", #data.records))
end

------------------------------
-- 主逻辑
------------------------------
local firstRun = true
local pendingSeed = nil

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(self, isContinued)
    Options.PauseOnFocusLost = false
    Game():GetHUD():SetVisible(false)
    local player = Isaac.GetPlayer(0)
    player.Visible = false

    pendingSeed = Game():GetSeeds():GetStartSeedString()

    self:Load()
    if data.state and data.state.phase > 0 and data.state.phase <= #TestItems then
        local item = TestItems[data.state.phase]
        if item.type == "collectible" then
            player:AddCollectible(item.id, Isaac.GetItemConfig():GetCollectible(item.id).InitCharge)
        elseif item.type == "trinket" then
            player:DropTrinket(player.Position + player.PositionOffset)
            player:AddTrinket(item.id, true)
            player:UseActiveItem(CollectibleType.COLLECTIBLE_SMELTER, 3339)
        end
    end
end)

mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function(self)
    self:Load()

    if firstRun then
        firstRun = false
        Isaac.ExecuteCommand("restart")
        return
    end

    data.records = data.records or {}

    if not data.state then
        data.state = {
            seed = pendingSeed,
            phase = 0,
            stageIndex = 1,
            bossPositions = {},
        }
    end

    local state = data.state
    local phaseKey = tostring(state.phase)
    state.bossPositions[phaseKey] = state.bossPositions[phaseKey] or {}

    local stageKey = Stages[state.stageIndex]
    Isaac.ExecuteCommand("stage " .. stageKey)

    local bossPos = self:GetBossPosition()
    state.bossPositions[phaseKey][stageKey] = bossPos

    state.stageIndex = state.stageIndex + 1

    if state.stageIndex > #Stages then
        state.stageIndex = 1
        state.phase = state.phase + 1

        if state.phase > #TestItems then
            -- 全部阶段完成，对比记录
            self:CompareAndRecord()
            -- 生成新种子，用当前种子+1派生
            local newSeed = Seeds.Seed2String(Game():GetSeeds():GetStartSeed() + 1)
            data.state = nil
            self:Save()
            Isaac.ExecuteCommand("seed " .. newSeed)
        else
            -- 进入下一阶段（带下一个道具），同种子重开
            self:Save()
            Isaac.ExecuteCommand("seed " .. state.seed)
        end
    else
        self:Save()
    end
end)

-- 禁用XL楼层
mod:AddCallback(ModCallbacks.MC_POST_CURSE_EVAL, function(self, curses)
    return ~LevelCurse.CURSE_OF_LABYRINTH & curses
end)

------------------------------
-- 渲染
------------------------------
mod:AddCallback(ModCallbacks.MC_POST_RENDER, function(self)
    local pos = Vector(15, 20)
    local renderSize = 0.5
    local lineHeight = 8

    -- 显示当前测试状态
    if data.state then
        local state = data.state
        local phaseInfo
        if state.phase == 0 then
            phaseInfo = "基准(无道具)"
        elseif state.phase <= #TestItems then
            phaseInfo = TestItems[state.phase].name .. "(" .. TestItems[state.phase].id .. ")"
        else
            phaseInfo = "对比中..."
        end
        local text = string.format("种子: %s | 阶段: %d/%d %s | 楼层: %d/%d",
            state.seed or "?",
            state.phase, #TestItems,
            phaseInfo,
            math.min(state.stageIndex, #Stages), #Stages)
        Isaac.RenderScaledText(text, pos.X, pos.Y, renderSize, renderSize, 1, 1, 0, 1)
        pos.Y = pos.Y + lineHeight * 2
    end

    -- 显示已有记录
    if data.records and #data.records > 0 then
        Isaac.RenderScaledText("--- 差异记录 ---", pos.X, pos.Y, renderSize, renderSize, 0, 1, 1, 1)
        pos.Y = pos.Y + lineHeight

        local seedCount = 0
        local lastSeed = nil
        for i, record in ipairs(data.records) do
            if record.seed ~= lastSeed then
                seedCount = seedCount + 1
                lastSeed = record.seed
            end

            local text
            if record.diff_count > 0 then
                local stageList = {}
                for _, diff in ipairs(record.diff_stages) do
                    table.insert(stageList, diff.stage)
                end
                text = string.format("[%s] %s(%d): %s",
                    record.seed, record.item_name, record.item_id,
                    table.concat(stageList, ","))
                Isaac.RenderScaledText(text, pos.X, pos.Y, renderSize, renderSize, 1, 0.3, 0.3, 1)
            else
                text = string.format("[%s] %s(%d): 无差异",
                    record.seed, record.item_name, record.item_id)
                Isaac.RenderScaledText(text, pos.X, pos.Y, renderSize, renderSize, 0.5, 1, 0.5, 1)
            end
            pos.Y = pos.Y + lineHeight

            if pos.Y > 500 then
                Isaac.RenderScaledText("...(更多记录请用控制台 lua BDCShowRecords() 查看)",
                    pos.X, pos.Y, renderSize, renderSize, 0.5, 0.5, 0.5, 1)
                break
            end
        end

        pos.Y = pos.Y + lineHeight
        Isaac.RenderScaledText(
            string.format("已测试 %d 个种子，共 %d 条记录", seedCount, #data.records),
            pos.X, pos.Y, renderSize, renderSize, 0.7, 0.7, 0.7, 1)
    else
        Isaac.RenderScaledText("暂无差异记录 (测试中...)", pos.X, pos.Y, renderSize, renderSize, 0.5, 0.5, 0.5, 1)
    end
end)

mod:AddCallback(ModCallbacks.MC_PRE_MOD_UNLOAD, function(self)
    Options.PauseOnFocusLost = true
end)
