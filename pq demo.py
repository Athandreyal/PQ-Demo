import json, random, sys, operator

time=0
#for how many weapons reach the TG
hits=0
#for how many missiles are shot down
kills=0

#constants - these are configurable from within the script as well.
#how much the internal priorities rise per increment they didn't shoot
priorityIncrement = 2
#should the queue be static order, or interleaved round robin
roundRobin=True
#should it wait after every time incrment for the user to move on, or just run until a magazine is empty and then wait.
waitEach=True
#should it print the lines for each shot taken?
showShots = True
#should it print the lines for each missile?
showVampires = True
#should it print the lines for the shot queue?
showQueue = True
#should it obey missile range bands?
rangeBands = True
#should it obey salvo limits?
salvoLimits = True
#should it use mixed or uniform ammo?
mixedAmmunition = False

#note, speeds and ranges are in thousands of km
missiles = {"Asp":{'type':'AMM','range':4500},
            "Taipan":{'type':'AMM','range':17000},
            "RingNeck":{'type':'AMM','range':700}}


#FC's have priorities and references to launchers
class FC:
    def __init__(self,i,pb):
        self.priorityBase = pb
        self.priorityInternal = pb
        self.launchers = {}
        self.id = i
        self.ready=True
        self.salvoQtyLimit=None
        self.salvoSizeLimit=None
        self.rangeMin=None
        self.rangeMax=None
        self.weaponRange=None
        self.ship=None
    #adds a launcher to the FC
    def addLauncher(self,launcher):
        try:
            self.launchers[len(self.launchers.keys())] = launcher
        except:
            self.launchers[0] = launcher
        launcher.FC=self
        self.weaponRange=launcher.range
    #sets the priority of the FC
    def setPriority(self,p):
        self.priorityBase = p
        self.priorityInternal = self.priorityBase
    #resets the current priority, to the default
    def reset(self):
        self.priorityInternal=self.priorityBase
        self.ready=True
    #determines how many assigned launchers are currently ready to fire
    def readyCount(self):
        return sum(launcher.ready() for launcher in self.launchers.values())
    #determines what, if any, weapons are loaded.
    def getWeapon(self):
        for launcher in self.launchers:
            if self.launchers[launcher].weapon is not None:
                return self.launchers[launcher].weapon
        return None
    #determines if FC is ready to engage targets
    def isReady(self):
        return self.readyCount() > 0
    #shoots assigned launchers which are ready, at the target
    def shoot(self,magazine,qty):  #doesn't need to verify the target, Its presumed if we call this that the weapon has been verified as a valid target
        shot=False
        for launcher in self.launchers.values():
            if launcher.weapon is not None:
                if qty > 0:
                    shot=True
                    qty-=1
                    self.ready=False
                    magazine.reload(launcher)
        if shot:
            self.priorityInternal=self.priorityBase
    #iterates over assigned launchers, advancing their reload progress
    def iterLaunchers(self):
        if not self.ready:
            self.ready=True
        else:
            self.priorityInternal += priorityIncrement
        for launcher in self.launchers:
            self.launchers[launcher].reloading -= 5
            if self.launchers[launcher].reloading < 0:
                self.launchers[launcher].reloading = 0
    def __str__(self):
        s = "FC " +str(self.id) + ': ' + 'Priority:' + str(self.priorityBase)+'\n'
        launchers = [self.launchers[x] for x in self.launchers.keys()]
        for l in launchers:
            s += str(l)
        s += '\n'
        return s

#launchers have reload lengths
class Launcher:
    def __init__(self,id_n, reload, weapon):
        self.reloadTime = reload
        self.reloading = 0
        self.weapon = weapon
        self.range = missiles[weapon]['range']
        self.FC=None
        self.id=id_n
    #assigns the given weapon, and sets reloading to reload time
    def loadMissile(self,weapon):
        self.weapon=weapon
        self.reloading=self.reloadTime
    #configures a launcher with a weapon and ID without the 'loading' process
    def set(self,n,weapon):
        self.id=n
        self.weapon=weapon
    #is the launcher ready to fire?
    def ready(self):
        return self.weapon is not None and self.reloading==0
    def __str__(self):
        s = '\tL' + str(self.id) +': '+ self.weapon if self.weapon is not None else ''
        if not self.ready() and self.weapon is not None:
            s+= '('+str(self.reloadTime-self.reloading)+' : ' + str(self.reloadTime) + ')'
        else:
            s+= ' (ready)'
        s+= '\n'
        return s

# magazines contain munitions
class Magazine:
    def __init__(self):
        self.contains = {}
    #reloads the given launcher, if there are more of that weapon in stock, else sets it to None
    def reload(self, launcher):
        if launcher.weapon in self.contains and self.contains[launcher.weapon] > 0:
            launcher.reloading=launcher.reloadTime
            self.contains[launcher.weapon] -= 1
        else:
            launcher.reloading=launcher.reloadTime
            launcher.weapon=None
    #adds more stock to the magazine.
    def add(self,weaponry):
        for weapon in weaponry:
            for w,q in weapon:
                if w in self.contains:
                    self.contains[w] += q
                else:
                    self.contains[w] = q
    #if the magazine is currently empty or not
    def isEmpty(self):
        if len(self.contains.keys()) == 0:
            return True
        return sum([self.contains[k] for k in self.contains.keys()]) == 0
    def __str__(self):
        length = max([len(s) for s in self.contains])
        s = 'Magazine:'
        if self.isEmpty():
            return s + ' Empty'
        for i in self.contains.keys():
            s+= '\n\t'+i + ':' + ' '*(length-len(i)) + '  ' + str(self.contains[i])
        return s + '\n'
        

#ships have FC and launchers.
class Ship:
    def __init__(self,short,name):
        self.name=name
        self.short=short
        self.launchers={}
        self.FC = {}
        self.Mag=Magazine()
        self.TG=None
    #adds a fire control to the ship
    def addFC(self,fc):
        if not self.FC:
            self.FC[0]=fc
        else:
            self.FC[len(self.FC.keys())] = fc
    #adds a list of firecontrols to the ship
    def addFCs(self,qty,pri):
        for n in range(qty):
            self.addFC(FC(n,pri))
    #reseta all firecontrols to default ready state
    def resetFCs(self):
        for fc in self.FC:
            self.FC[fc].reset()
    #adds a launcher to the ship
    def addLauncher(self,launcher):
        self.launchers[len(self.launchers.keys())] = launcher
    #pairs a launcher with a firecontrol
    def assignLauncher(self,fc,launcher):
        self.FC[fc].addLauncher(self.launchers[launcher])
    #set's a laucher to loaded, with the given weapon
    def setLaunchers(self,launchers,weapon):
        for l in launchers:
           self.launchers[l].set(weapon)
    #shoots a firecontrol at an incoming salvo
    def shoot(self, fc, salvo, shoot_qty):
        salvo.intercepted(shoot_qty)
        fc.shoot(self.Mag,shoot_qty)
        fc.priorityInternal=fc.priorityBase
    def __str__(self):
        s = self.short+' '+self.name + '\n'
        s += str(self.Mag)
        for fc in self.FC:
            s+= str(self.FC[fc])
        unassigned = [self.launchers[x] for x in self.launchers.keys() if self.launchers[x].FC==None]
        if unassigned:
            s += 'Unassigned:\n'
            for l in unassigned:
                s+=str(l)
        return s + '\n'

#task groups have ships, and track incoming missiles
class TaskGroup:
    def __init__(self,name,ships):
        self.name=name
        self.ships=ships
        for ship in self.ships:
            self.ships[ship].TG=self
        self.q=PQ()
        self.vampires = {}
        self.createFCQueue()
        self.PDSalvo=0
        self.PDFire=0
        self.busyPD=0
    #sets the fleet's point defence capacity
    def setPDCapacity(self,pdc):
        self.PDSalvo = pdc[0]
        self.PDFire = pdc[1]
    #adds a ship or ships to the task group, and add's their firecontrols to the firing queue
    def addShips(self,ships):
        for ship in ships:
            ship.TG=self
            if ship.name not in self.ships:
                self.ships[ship.name] = ship
                f = 0
                for fc in ship.FC:
                    ship.fc[fc].priorityInternal+=f
                    self.q.insert((ship.fc[fc],ship))
                    f+=1
    def __str__(self):
        s = 'TaskGroup '+self.name+'\n\t'
        for ship in self.ships:
            name = self.ships[ship].short+' '+self.ships[ship].name
            s+= '\n\t'+name
            for item in self.ships[ship].Mag.contains:
                s+= '\n\t\t' + item+': '+str(self.ships[ship].Mag.contains[item])+'\n'
        return s
    #prints more than the default __str__ does
    def fullString(self):
        s = 'TaskGroup '+self.name+'\n'
        for ship in self.ships.keys():
            s+= str(self.ships[ship])
        return s
    #iterates over the ships present and creates a firing queue
    def createFCQueue(self):
        for ship in self.ships.values():
            f = 0
            for fc in ship.FC.values():
                fc.priorityInternal+=f
                self.q.insert((fc,ship))
                f +=1
    #asks the queue for which firing control should shoot next
#    def getSHooter(self):
#        return self.q.getShooter()
    #places a missile salvo into the incoming vampires dict
    def registerVampire(self,vamp):
        if not vamp.TTI in self.vampires:
            self.vampires[vamp.TTI] = [vamp]
        else:
            self.vampires[vamp.TTI].append(vamp)
    #removes a missiles salvo from the incoming missiles dict
    def unRegisterVampire(self,vamp):
        del self.vampires[vamp.TTI][vamp.name]
        if not self.vampires[vamp.TTI]:
            del self.vampires[vamp.TTI]
    #evaluates the FC's in the firing queue, and attempts to open fire, returning true if it did, false if not.
    def engagedTargets(self):
        for fc_p in self.q.getQueue():
            ship = fc_p[1]
            fc = fc_p[0]
            if fc.ready and fc.isReady():
                salvo = self.selectTarget(fc)
                if salvo is not None:
                    shootQty = 0
                    if fc.salvoSizeLimit is not None and salvo.qty-fc.salvoSizeLimit > 0:
                        shootQty = salvo.qty- fc.salvoSizeLimit if salvoLimits else 0
                        if shootQty > fc.readyCount():
                            shootQty=fc.readyCount()
                    else:
                        shootQty=min(fc.readyCount(),salvo.qty)
                    if salvo is not None and salvo.qty > 0 and shootQty > 0:
                        if showShots:
                            print(ship.short+' '+ship.name+' shoot FC'+str(fc.id)+': ' + str(fc.getWeapon())+' '+str(shootQty) + ' -> '+ str(salvo))
                        ship.shoot(fc,salvo,shootQty)
        return False
    #iterates the list of incoming salvos, for each iterates the list of firecontrols, and tries to engage all targets with all firecontrols.
    def selectTarget(self,fc):
        for TTI in self.vampires.values():
            too_many_salvos = fc.salvoQtyLimit is not None and len(TTI) > fc.salvoQtyLimit
            smallest=None
            largest=None
            range_minimum = 0 if fc.rangeMin is None else fc.rangeMin
            range_maximum = fc.weaponRange if fc.rangeMax is None else min(fc.weaponRange,fc.rangeMax)
            for salvo in TTI.values():
                if range_minimum <= salvo.range <= range_maximum:  #the salvo range is within the range band of the weapon and FC
                    if fc.salvoQtyLimit is None and fc.salvoSizeLimit is None:
                        #then we don't care and the first salvo we can reach is to be engaged
                        return salvo
                    if smallest == None:
                        smallest=salvo
                    else:
                        if salvo.qty < smallest.qty:
                            smallest=salvo
                    if largest == None:
                        largest=salvo
                    else:
                        if salvo.qty > largest.qty:
                            largest=salvo
            if too_many_salvos and smallest is not None and range_minimum <= smallest.range <= range_maximum:
                #too many salvos inbound, kill the smallest salvo
                return smallest
            elif fc.salvoSizeLimit is not None and largest is not None and largest.qty > fc.salvoSizeLimit and range_minimum <= largest.range <= range_maximum:
                #some salvos are too large, kill the largest one
                return largest
        return None  #if we make it here, we rejected every target.  Possibly all targets less than range min, or more than rangemax, or within PD tolerances.    
    #moves the incoming missile salvos, according tot he r speed.  Essentially only decreased range to target.
    def move(self):
        allSalvos = []
        for TTI in self.vampires:
            for salvo in self.vampires[TTI]:
                allSalvos.append(self.vampires[TTI][salvo])
        for eachSalvo in allSalvos:
            eachSalvo.move()
    #resets the priorities of each firecontrol in the taskgroup to their defaults
    def resetPriorities(self):
        for fc in self.q.queue:
            fc[0].reset()
    #resets each FC for each new increment, flagging it as available ot use, and iterating its launchers for reloading state.
    def FCReset(self):
        for fc in self.q.queue:
            fc[0].iterLaunchers()
    #resets the task group point defence capacity
    def PDReset(self):
        self.busyPD=0

#missile salvos have missile details, and inform taskgroups that they are intended target
class Salvo:
    def __init__(self,name,qty,spd_kks,target,range_kkm):
        self.name=name
        self.qty=qty
        self.spd=spd_kks
        #reference to ship object
        self.target=target
        self.range=range_kkm
        self.lastTargetTG=None
        self.targetTG=target.TG
        self.TTI=self.getTTI()
        self.registerTarget()
    #returns the time to intercept, in seconds, is always a multiple of 5 given the game's 5 second increments.
    def getTTI(self):#time to intercept
        return int(-(-self.range // (self.spd*5))*5)
    #this salvo has been firedupon, currently assumed 100% kill rate
    def intercepted(self, qty):
        global kills
        self.qty-=qty
        kills+=qty
        if self.qty==0:
            self.unRegisterTarget()
    #performs the missile movement process, and if necessary, handles point defence evaluation
    def move(self):
        global hits
        self.unRegisterTarget()
        self.range -= self.spd*5
        if self.range < 0:  #intercepted, handle PD fire
            if self.targetTG.busyPD < self.targetTG.PDSalvo:
                if self.qty > self.targetTG.PDFire:  #hits, else dead salvo to PD fire
                    self.intercepted(self.targetTG.PDFire)
                    hits+=self.qty
                    print('PD Kill -> %dx%s '%(self.targetTG.PDFire,(str(self).split(' ',1))[1]))
                    print('IMPACT',self)
                    self.targetTG.busyPD+=1
                else:
                    print('PD Kill ->',self)
                    self.targetTG.busyPD+=1
            else:
                hits+=self.qty
                print('IMPACT',self)
        else:
            self.TTI=self.getTTI()
            self.registerTarget()
    def __str__(self):
        return str(self.qty)+'x '+self.name + ': ' + str(self.spd)+'kkm/s '+str(max(0,self.range))+'kkm, -> '+self.target.TG.name+' '+self.target.short+' '+self.target.name+',  TTI: '+str(self.TTI)+' sec'
    #registers the missile salvo with its target
    def registerTarget(self):
        if self.targetTG==None:
            return
        tg = self.targetTG
        TTI = self.getTTI()
        if TTI not in tg.vampires:
            tg.vampires[TTI] = {self.name:self}
        elif self not in tg.vampires[TTI]:
            tg.vampires[TTI][self.name] = self
    #un-registers the missile salvo with its target
    def unRegisterTarget(self):
        if self.targetTG==None:
            return
        #print('unregistering target')
        tg = self.targetTG
        TTI = self.getTTI()
        del tg.vampires[TTI][self.name]
        if not tg.vampires[TTI]:
            del tg.vampires[TTI]


#modified variant of a priority queue
class PQ():
    def __init__(self):
        self.queue = []
        self.unsorted=[]
    #wrapper to return the queue
    def getQueue(self):
        return tuple(self.queue)
    #is the queue empty?
    def isEmpty(self):
        return len(self.queue)==0
    #add firecontrol pairs to the queue, which are both an FC and the ship it is assigned to
    def insert(self,fc_pair):
        self.queue.append(fc_pair)
        self.reSort()
        return
    #sorts the queue based on its current internal priorities
    def reSort(self):
        self.queue = [x for x in self.queue if x[0].getWeapon() is not None]
        if roundRobin:
            self.queue = sorted(self.queue,key = lambda x : (-x[0].priorityInternal+x[0].id,x[1].name))
        else:
            self.queue = sorted(self.queue,key = lambda x : x[1].name)
    #advanced firecontrol priorities as time goes by and they don't get to shoot.
    def increment(self):
        if not roundRobin:
            return
        for p in self.queue:
            p[0].priorityInternal+=1
    #resets the priorities of every firecontrol int he queue
    def reset(self):
        for p in self.queue:
            p[0].priorityInternal=p[0].priorityBase
    #returns the first fc in the queue, which is ready to shoot something.
    def getShooter(self):
        for p in self.queue:
            if p[0].ready and p[0].readyCount() > 0:
                return p
    def __str__(self):
        s = ''
        priorityLengths = len(str(max([p[0].priorityInternal for p in self.queue])))
        for fp in self.queue:
            fc,ship = fp
            weaponNameLength = max([len(w) for w in ship.Mag.contains])
            rangeLength = max([len(str(missiles[r]['range'])) for r in ship.Mag.contains])
            s+='\n'+ship.short+' '+ship.name+'\t'+str(fc.launchers[0].weapon)+' '*(weaponNameLength-len(fc.getWeapon() if fc.getWeapon() is not None else 'None'))+' '
            r = (rangeLength-len(str(fc.weaponRange)))*' '+'%dk km'%fc.weaponRange if fc.getWeapon() is not None else '         '
            w = ' ' if fc.getWeapon() not in ship.Mag.contains else str(ship.Mag.contains[fc.getWeapon()])
            s+= r + '  ' + w+'\t'
            if roundRobin:
                s+= '\tpri: '+(priorityLengths-len(str(fc.priorityInternal)))*' '+str(fc.priorityInternal)
            s+='  FC: '+str(fc.id)+' Ready: '+str(fc.readyCount())+' / ' +str(len(fc.launchers))
            if not fc.ready:
                s+=' fc busy'
            else:
                s+='        '
            if fc.readyCount() < len(fc.launchers) and min([fc.launchers[x].reloading for x in fc.launchers]) > 0:
                s+=' reloading ' + str(min([fc.launchers[x].reloading for x in fc.launchers])) + 's'
        return s

#generates a default taskgroup suitable for demoing the concept
def preloadTG(tgName, mixed=True):
    short='DDG'
    names='Barry','Stout','Mitscher','Cole'
    if mixed:
        mag1 = [['Asp',48],['Taipan',120],['RingNeck',120]]
        launcher_loads = ['Taipan']*6 + ['Asp']*6 + ['RingNeck']*6
        launcher_rates =       [10]*6 +    [10]*6 +         [10]*6
        fc_assign      =        [0]*6 +     [1]*6 +          [2]*6
        range_bands = {'Asp':[700,4500],'Taipan':[4500,17000],'RingNeck':[0,700]}
    else:
        mag1 = [['Taipan',200]]
        launcher_loads = ['Taipan']*12
        launcher_rates =       [10]*12
        fc_assign      =        [0]*4 +     [1]*4 +          [2]*4
        range_bands = {'Taipan':[0,17000]}
    FC = 3,3
    ships = {}
    for name in names:
        s=Ship(short,name)
        s.Mag.add([mag1])
        for n in range(min(len(launcher_loads),len(launcher_rates),len(fc_assign))):
            s.addLauncher(Launcher(n,launcher_rates[n],launcher_loads[n]))
        s.addFCs(FC[0],FC[1])
        for n in range(len(s.launchers.keys())):
            s.assignLauncher(fc_assign[n],n)
            if rangeBands:
                s.FC[fc_assign[n]].rangeMin=range_bands[launcher_loads[n]][0]
                s.FC[fc_assign[n]].rangeMax=range_bands[launcher_loads[n]][1]
            if salvoLimits:
                s.FC[fc_assign[n]].salvoQtyLimit=4
                s.FC[fc_assign[n]].salvoSizeLimit=8
            s.FC[fc_assign[n]].ship=s
        ships[s.name] = s
    tg = TaskGroup(tgName,ships)
    tg.setPDCapacity([4,8])  #4 salvos, 8 misisles/salvo
    tg.resetPriorities()
    return tg

#generates a number of missile salvos
vamp_num = 0
def initSalvos(tg,n):
    global vamp_num
    qty = random.randint(4,12)
    speed = 300
    range_kkm = random.randint(max(1000,int(speed*15)),16500)
    while n > 0:
        name = 'Vampire '+str(vamp_num)
        vamp_num+=1
        target = random.choice(list(tg.ships.values()))
        
        Salvo(name,qty,speed,target,range_kkm)
        n-=1
#prints the missile salvos
def printVampires(vamps):
    for TTI in sorted(vamps.keys(),reverse=True):
        print("TTI: ",TTI)
        for salvo in vamps[TTI]:
            print('\t',vamps[TTI][salvo])
 
 #executes the demonstration process
def demonstration(TG):
    global time
    global hits
    global kills
    time=0
    hits=0
    kills=0
    
    initSalvos(TG,10)
    #print(TG1.vampires)
    allStocked=True
    interval=0
    while allStocked:
        if interval >= 30:
            initSalvos(TG,random.randint(2,10))
            interval = 0
        engaged = True
        if showVampires:
            printVampires(TG.vampires)
            print('')
        while engaged:
            engaged = TG.engagedTargets()
            for ship in TG.ships:
                allStocked = allStocked and sum([m for m in TG.ships[ship].Mag.contains.values()])>0
        time+=5
        interval+=5
        TG.move()
        TG.PDReset()
        
        if showQueue:
            print(TG.q)
        TG.FCReset()
        if roundRobin:
            TG.q.reSort()
        if waitEach:
            x = input('\none time increment complete, press enter to continue\n or type in quit and then press enter to abort the demonstration: \n\n')
            if x.upper() == 'QUIT':
                print('demonstration aborted')
                return
        if waitEach or showShots or showVampires or showQueue:
            print('\n\n')
    print(TG)
    print('combat ended in',time,'seconds')
    print('task group killed',kills,'missiles')
    print('task group was hit',hits,'times')

#menu code to edit the priorities of a ship's FC, to allow exploring the effect of a priority on the firing queue
def changeFCPriorities(TG):
    editingShip=True
    while editingShip:
        n=1
        print('')
        for ship in sorted(TG.ships.keys()):
            print('%d)'%n,TG.ships[ship].short+' '+TG.ships[ship].name)
            n+=1
        print('\n0) return')
        n = getint('\nwhich ship do you want to change priorities for? ',0,n-1)
        ship = TG.ships[sorted(TG.ships.keys())[n-1]]
        if n == 0:
            editingShip = False
        if editingShip:
            editingFC=True
            while editingFC:
                n=1
                for fc in sorted(ship.FC.keys()):
                    print('%d)'%n,ship.FC[fc])
                    n+=1
                print('\n0) return')
                n = getint('\nwhich FC do you want to change priorities for? ',0,n-1)
                if n == 0:
                    editingFC = False
                if editingFC:
                    FC = ship.FC[sorted(ship.FC.keys())[n-1]]
                    n = getint('\nLarger values increase usage priority.  Arbitrary maximum is 1000.  What is the new priority? ',0,1000)
                    FC.priorityBase = n
                    FC.reset()
#simplistic user input scrubbing to only accept integers.
def getint(text, minimum, maximum):
    incomplete = True
    while incomplete:
        choice = input(text)
        choice2 = ''.join(x for x in choice if 48 <= ord(x) <= 57)
        if choice != choice2:
            print("        Rejecting characters which are not numbers...")
        try:
            choice2 = int(choice2)
            if minimum <= choice2 <= maximum:
                incomplete = False
            else:
                print( "        Please choose one of the options given, %s wasn't an option." % choice2)
        except:
            choice2 = None
            print( "        Please choose one of the options given, %s wasn't an option..." % choice2)
    return choice2

def menu():
    print(' 1) toggle queue ordering? Currently','interleaved round robin' if roundRobin else 'aurora standard')
    print(' 2) toggle waiting for keypress after every firing cycle? Currently','waiting on each firing cycle' if waitEach else 'Running until exhausted')
    print(' 3) toggle show firing queue every cycle? Currently','showing' if showQueue else 'not showing')
    print(' 4) toggle show salvo list? Currently','showing' if showVampires else 'not showing')
    print(' 5) toggle show shots taken? Currently','showing' if showShots else 'not showing')
    print(' 6) toggle min/max range bands? Currently','enabled' if rangeBands else 'disabled')
    print(' 7) toggle salvo size/qty enabled? Currently','enabled' if salvoLimits else 'disabled')
    print(' 8) toggle mixed ammunition types? Currently','mixed' if mixedAmmunition else 'not mixed')
    print(' 9) show taskgroup')
    print('10) change FC priorities')
    print('11) reset Task group - restores magazines and resets priorities')
    print('12) perform firing cycle demonstration')
    print(' 0) exit')

#main loop of the script, repeats menu and performs action user selected
def begin():
    global roundRobin
    global waitEach
    global showQueue
    global showVampires
    global showShots
    global rangeBands
    global salvoLimits
    global mixedAmmunition
    running = True
    TG=preloadTG('TG1',mixedAmmunition)
    while running:
        print('')
        menu()
        print('')
        choice = getint('Your choice is?: ',0,12)
        if choice == 1:
            roundRobin = not roundRobin
            TG.q.reSort()
        elif choice == 2:
            waitEach = not waitEach
        elif choice  == 3:
            showQueue = not showQueue
        elif choice == 4:
            showVampires = not showVampires
        elif choice == 5:
            showShots = not showShots
        elif choice == 6:
            rangeBands = not rangeBands
            for ship in TG.ships.values():
                for fc in ship.FC.values():
                    fc.rangeMin = None
                    fc.rangeMax = None
        elif choice == 7:
            salvoLimits = not salvoLimits
            for ship in TG.ships.values():
                for fc in ship.FC.values():
                    fc.salvoQtyLimit = None
                    fc.salvoSizeLimit = None
        elif choice == 8:
            mixedAmmunition = not mixedAmmunition
            print('resetting the task Group')
            TG=preloadTG('TG1',mixedAmmunition)
        elif choice == 9:
            print(TG.fullString())
        elif choice == 10:
            changeFCPriorities(TG)
        elif choice == 11:
            TG=preloadTG('TG1',mixedAmmunition)
        elif choice == 12:
            demonstration(TG)
            print('resetting the task Group')
            TG=preloadTG('TG1',mixedAmmunition)
        elif choice == 0:
            sys.exit()
    
if __name__ == '__main__':
    begin()
