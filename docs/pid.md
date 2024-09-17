## August 2024: Fluidics troubleshooting/PID parameters

### Problem
In Kilroy, Sophie would set the target flow rate to higher than currently measured, and the pressure on the OB1 would go up accordingly;
however, when Sophie set the target flow rate to zero or lower than currently measured, the pressure on the OB1 would not go down.

### Troubleshooting process
There turned out to be various problems at play, such as that certain ports on certain valves were not flowing properly, and the flow sensor
would sometimes get stuck. We also spent considerable time checking whether the SDK function calls in both Kilroy and our test scripts were
being called with the correct parameters and in the correct order. In the end, however, we realized that actually the OB1 pressure was
responding correctly all along to lower-than-present target flow rates; the problem was just that there was **a delay in its response** on the 
order of about 10 minutes.

### PID values
We discovered that setting different PID values fixed the delay issue. Previously, Sophie had been setting P=1 and I=4; these were values that 
she obtained by tuning the loop interactively in ESI, and these values worked well (meaning the pressure increased/decreased according to the
target flow rate, and did so within a few seconds) while interacting with the fluidics using the ESI interface. Sophie had been told by Elveflow
personnel that the PID values tuned in ESI should transfer over to the SDK, and it makes sense that they would; however, for reasons we have not
yet figured out, P=1 and I=4 do not seem to work well in the SDK. Instead, from the "default" values in the example script (P=10 and I=0.1) we
raised P to 20 and decreased I to 0.001, and then the pressure was responsive within seconds.

### Analysis
1. It makes sense to me that parameters P=1 and I=4 were causing a huge time delay: the I term is the integration of the error over time, so if
   the I coefficient is much bigger than the P coefficient (the proportional), then essentially we have **tuned the loop such that the historical
   error is weighted much more than the present error**. This means that, for example, if first we set the target flow rate to something high
   (such that the error is positive, say 10), left it for 5 seconds or 5 minutes or whatever (not enough in the current setup for the actual
   flow rate to catch up), and then set the target flow rate to zero or lower (such that the error is negative, say -10), then for 5 seconds or
   5 minutes or whatever,the "error over time" is still positive (though decreasing). If I is much bigger than P, then the positive error from
   the I term overwhelms the current negative error from the P term. Furthermore, if (as was the case in our setup) the actual flow rate was
   hovering/stuck around 10 and we were testing with a "high" flow rate of 30 versus a "low" flow rate of 0, then since 30-10=20 and 0-10=-10,
   it takes even longer for the negative error of 10 to "unwind" the relatively larger positive error of 20.
1. I don't know why P=1/I=4 worked well in ESI and I don't know why the behavior is different in the SDK. (Different units??)
1. This also explains why, while working with the test script and before changing the PID values, we were seeing that the pressure would respond
   correctly to the _first_ target flow rate, regardless of if the target was higher or lower than the measured value, but then it would get 'stuck'
   thereafter and not respond to the next target flow rate until after a highly variable delay. The variable delay initially made it seem like the
   delay was not in fact directly related to the PID parameters, but now it is clear to me that the delay varies depending on both the difference
   between the positive vs the negative error, and the amount of time we waited between setting the first target flowrate and setting the second
   target flowrate (!!).

### Other Notes
The PID parameters that we are currently settled on (P=20,I=0.001; NB: the Elveflow software's PID loop doesn't let the user set the Derivative 
coefficient) are just what Zoe landed on after seeing that they satisfactorily fixed the enormous delay issue. However, if P is too big, there 
could be a problem with a violently oscillating system. It seems to me that the flow rate responds so slowly to pressure changes that this won't 
be a problem, but I don't have a complete sense of the rhythm of a real experiment, and also maybe the system will be more responsive after all 
the fluidics are physically well oiled and running etc. So, basically, further tuning of the P and I values might be required, but this requires 
fuller knowledge of the final desired and final actual behavior of the fluidics setup.
