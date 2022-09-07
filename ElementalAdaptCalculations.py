
from importlib.machinery import SourcelessFileLoader
import json
import os.path
import fnmatch
import math
import matplotlib.pyplot as plt

from numpy import roll

def readJSON(path):
    with open(path,'r') as f:
        data = json.load(f)
    return data

def cr_to_float(cr_in):
        if cr_in == "1/8":
            return 0.125
        elif cr_in == "1/4":
            return 0.25
        elif cr_in == "1/2":
            return 0.5
        elif isinstance(cr_in, dict):
            return float(cr_in["cr"])
        elif cr_in == []:
            return ""
        elif cr_in == "Unknown":
            return 0.0 #Appears to be when statblock doesn't exist, but entry is for a single CoS token
        else:
            return float(cr_in)

def find_field(monster,field):
    if field in monster:
        return monster[field]
    elif "_copy" in monster:
        return find_field(monster_lookup(monster["_copy"]["source"],monster["_copy"]["name"]),field)
    else:
        #print("field not found",monster["name"],field)
        return []

def monster_lookup(source, name):
        lookupdata = dataCache[index[source]]
        for lookupmonster in lookupdata["monster"]:
            if lookupmonster["name"].lower()==name.lower():
                return lookupmonster

def damage_calc(sources,weightFunction,dataCache):
#Calculates expected damage done assuming a constant (premodifier) ammount done to each creature
#in sources, with expectation weighted by weightFunction.

    totalWeight = 0 #This keeps a total of all the weightings applied
    normalDamage={} #This is the total damage dealt
    resDamage={}    #This is the total damage dealt through resistance, equivalently this
                    #   is the total damage resisted
    
    #Initalise all values to 0
    for dtype in damageTypes:
        normalDamage[dtype]=0.0
        resDamage[dtype]=0.0
    
    #Loop through every source and every monster in those sources
    for file in sources:
        data = dataCache[file]
        monsters = data["monster"]
        for monster in monsters:
            #Find the weighting from the cr (could possibly condense to one line)
            dmgweight,distweight = weightFunction(monster)

            totalWeight+=distweight

            #Don't do all the work if weight is 0
            if dmgweight!=0 and distweight!=0:

                #Find the list of damge types each type of modifier applies to
                dmgmods = [["resist",[]],["immune",[]],["vulnerable",[]]]
                if "_copy" in monster:
                    for mod in dmgmods:
                        mod[1] = find_field(monster,mod[0])
                else:
                    for mod in dmgmods:
                        if mod[0] in monster:
                            mod[1]=monster[mod[0]]
                for mod in dmgmods:
                    if mod[1] is None:
                        mod[1] = []
                
                #For each damagetype add the appropriate amount of damage dealt to the monster
                #(after modifiers) weighted by 'weight' calculated previously
                for dtype in damageTypes:
                    rdmg = 0.0
                    ndmg = 1.0
                    if dtype in dmgmods[0][1]:
                        ndmg = rdmg = 0.5
                    elif dtype in dmgmods[1][1]:
                        ndmg = 0.0
                    elif dtype in dmgmods[2][1]:
                        ndmg = 2.0
                    normalDamage[dtype]+=ndmg*distweight*dmgweight
                    resDamage[dtype]+=rdmg*distweight*dmgweight

    return normalDamage,resDamage,totalWeight

cr_max = 30    #max and min are inclusive, i.e. cr_min <= cr <= cr_max
cr_min = 0.125 #Only used in defining weighting functions below
def Uniform_Weight(monster):
    cr = cr_to_float(find_field(monster,"cr"))
    if cr == "":
        return 0.0,0.0
    if cr>cr_max or cr<cr_min:
        return 0.0,0.0
    return 1.0,1.0

def InverseCR_Weight(monster):
    cr = cr_to_float(find_field(monster,"cr"))
    if cr == "":
        return 0.0,0.0
    if cr>cr_max or cr<cr_min:
        return 0.0,0.0
    if cr == 0.0:
        return 0.0,0.0
    return (1.0/cr)**0.2,(1.0/cr)**0.2

def saveDC_Generator(saveDC,stat,distWeight):
    def save_Weight(monster):
        saves = find_field(monster,"save")
        statvalue = find_field(monster,stat)
        if stat in saves:
            prof = float(saves[stat][1:])
            if saves[stat][:1]=="-":
                prof = -prof
        else:
            prof=0
        saveBonus = prof + math.floor(statvalue/2 - 5)
        rollRequired = saveDC-saveBonus
        if rollRequired <= 1:
            damageMult = 0.5
        elif rollRequired >= 21:
            damageMult = 1
        else:
            damageMult = 1-(0.5*(21 - rollRequired)*0.05)
        return damageMult,distWeight(monster)[1]
    return save_Weight

def attack_Generator(attackBonus,distWeight):
    def attack_Weight(monster):
        ac = find_field(monster,"ac")

        if isinstance(ac,list):
            ac = ac[0]
        if isinstance(ac,dict):
            ac = ac["ac"]
        
        rollRequired = ac-attackBonus
        if rollRequired <= 1:
            damageMult = 1.0
        elif rollRequired >= 21:
            damageMult = 0.0
        else:
            damageMult = (21-rollRequired)/20
        return damageMult,distWeight(monster)[1]
    return attack_Weight

#Where to find all the .json files
pathDirectory = os.path.join(os.getcwd(),'data','bestiary')

#An index to convert from sources referenced in monster objects to actual file names
index = readJSON(os.path.join(pathDirectory,'index.json'))

#define different lists of source materials
mainSource = ['bestiary-mm.json','bestiary-vgm.json','bestiary-mtf.json','bestiary-mpmm.json']
fizzSource = ['bestiary-ftd.json']
allSource = []
for file in os.listdir(pathDirectory):
    allSource.append(file)
allSource = fnmatch.filter(allSource,'bestiary*.json')

#Cache every source to avoid need to keep reading/writing
dataCache = {}
for file in allSource:
    with open(os.path.join(pathDirectory,file),'r') as f:
        dataCache[file] = json.load(f)

#Every damage type we are considering
damageTypes = ["acid","cold","fire","lightning","thunder"]

#### PROGRAM START ####

dc_list = []
save_damages={}
save_damages_feat={}
percent_increase={}
for dtype in damageTypes:
    save_damages[dtype] = []
    save_damages_feat[dtype] = []
    percent_increase[dtype]=[]
for dc in range(5,26):
    data = damage_calc(mainSource+fizzSource,saveDC_Generator(dc,"con",Uniform_Weight),dataCache)
    for dtype in damageTypes:
        save_damages[dtype].append(data[0][dtype]/data[2])
        save_damages_feat[dtype].append((data[0][dtype]+data[1][dtype])/data[2])
        percent_increase[dtype].append(100*data[1][dtype]/data[0][dtype])
    dc_list.append(dc)

fig,ax=plt.subplots()
for dtype in damageTypes:
    plt.plot(dc_list,save_damages_feat[dtype],label=dtype)
    plt.plot(dc_list,save_damages[dtype],label=dtype+"base")
plt.legend()
ax.set_xlabel("Effect save DC")
ax.set_ylabel("Expected Damage Multiplier")
ax.grid(True)
#plt.show()

data = damage_calc(allSource,InverseCR_Weight,dataCache)

print(data[1]["fire"]/data[0]["fire"])

