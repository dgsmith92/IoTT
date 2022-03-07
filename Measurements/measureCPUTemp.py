from gpiozero import CPUTemperature
import time


cpu = CPUTemperature()
while True:
    time.sleep(1)
    print(cpu.temperature)
    
