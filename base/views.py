from django.shortcuts import render,redirect
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Room,Topic
from django.http import HttpResponse
from .forms import RoomForm

# rooms=[
#     {'id':1,'name':'Lets learn Python'},
#     {'id':2,'name':'Design with me '},
#     {'id':3,'name':'Frontend Web Developers'},
# ]

def loginPage(request):
    if request.method=='POST':
        username=request.POST.get('username')
        password=request.POST.get('password')
        try:
            user=User.objects.get(username=username)
        except:
            messages.error(request,'Username or password is incorrect')
    context={

    }
    return render(request , 'base/login_register.html',context)
def home (request):
    q=request.GET.get('q')if request.GET.get('q') !=None else ''
    rooms=Room.objects.filter(Q(topic__name__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))
    topics=Topic.objects.all()
    rooms_count=rooms.count()
    context={'rooms':rooms ,'topics':topics,'rooms_count':rooms_count}
    return render(request,"base/home.html",context)

# esta funcion de la vista 
#se encarga de mostrar la pagina de la sala
#en la carpeta de 'templates'
#se renderiza con la funcion render
def room(request,pk):
    room=Room.objects.get(id=pk)
    context={'room':room}
    return render(request,"base/room.html",context)

def createRoom(request):
    form=RoomForm()
    if request.method=='POST':
        form =RoomForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
        

    context={'form':form}
    return render(request,'base/room_form.html',context)

def updateRoom(request,pk):
    room=Room.objects.get(id=pk)
    form=RoomForm(instance=room)

    if request.method=='POST':
        form=RoomForm(request.POST, instance=room) 
        if form.is_valid():
                form.save()
                return redirect('home')
    context={'form':form}
    return render(request,'base/room_form.html',context)



def deleteRoom(request,pk):
    room=Room.objects.get(id=pk)
    if request.method=='POST':
        room.delete()
        return redirect('home')
    return render(request,'base/delete.html',{'obj':room})