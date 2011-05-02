// Консольная программа для организации вывода данных для модуля USB3000
//******************************************************************************
#include <stdio.h>
#include <conio.h>
#include <math.h>
#include "Rtusbapi.h"

// аварийное завершение программы
void TerminateApplication(char *ErrorString, bool TerminationFlag = true);
// отображение ошибок выполнения программы
void ShowThreadErrorMessage(void);
// округление
WORD Round(double Data);

// функция потока вывода данных из РС в модуль
DWORD WINAPI ServiceWriteThread(PVOID /*Context*/);
// идентификатор потока вывода
HANDLE hWriteThread;
DWORD WriteTid;

// максимально возможное кол-во опрашиваемых виртуальных слотов
const WORD MaxVirtualSoltsQuantity = 127;
// определяем константу pi
const double M_PI = 3.14159265358979323846;

// текущая версия библиотеки Rtusbapi.dll
DWORD DllVersion;
// указатель на интерфейс модуля
IRTUSB3000 *pModule;
// название модуля
char ModuleName[10];
// скорость работы шины USB
BYTE UsbSpeed;
// серийный номер модуля
char ModuleSerialNumber[9];
// версия драйвера AVR
char AvrVersion[5];
// структура информации в ППЗУ модуля
RTUSB3000::FLASH fi;
// структура, содержащая информацию о версии драйвера DSP
RTUSB3000::DSP_INFO di;
// структура, содержащая параметры работы ЦАП
RTUSB3000::OUTPUT_PARS dp;

//max возможное кол-во передаваемых отсчетов (кратное 32) для ф. ReadData и WriteData()
DWORD DataStep = 64*1024;
// длина буфера для выводимых данных
DWORD WritePoints = 2*DataStep;
// указатель на буфер для выводимых данных
SHORT	*WriteBuffer;

// однократный отсчёт для ЦАП
SHORT DacSample;
// номер канала ЦАП
const WORD DacNumber = 0x0;
// частота  вывода данных
const double WriteRate = 100.0;

// параметры выводимого сигнала
double CurrentTime = 0.0; 			  				// в млс
const double SignalFrequency = 1.0; 	  		// в кГц
const double SignalAmplitude = 2000.0;			// в кодах ЦАП

// экранный счетчик-индикатор
DWORD Counter = 0x0, OldCounter = 0xFFFFFFFF;

// номер ошибки при выполнении потока сбора данных
WORD ThreadErrorNumber;
// флажок завершения потока вывода данных
bool IsThreadComplete = false;

//------------------------------------------------------------------------
// основная программа
//------------------------------------------------------------------------
void main(int argc, char** argv)
{
	WORD i;

	// зачистим экран монитора	
	system("cls");

	printf(" *******************************************\n");
	printf(" Console example of Data Writing to USB3000 \n");
	printf(" *******************************************\n\n");

	// проверим версию используемой библиотеки Rtusbapi.dll
	if((DllVersion = RtGetDllVersion()) != CURRENT_VERSION_RTUSBAPI) 
	{	
		char String[128];
		sprintf(String, " Rtusbapi.dll Version Error!!!\n   Current: %1u.%1u. Required: %1u.%1u",
											DllVersion >> 0x10, DllVersion & 0xFFFF,
											CURRENT_VERSION_RTUSBAPI >> 0x10, CURRENT_VERSION_RTUSBAPI & 0xFFFF);
		
		TerminateApplication(String);
	}		
	else printf(" Rtusbapi.dll Version --> OK\n");

	// получим указатель на интерфейс модуля USB3000
	pModule = static_cast<IRTUSB3000 *>(RtCreateInstance("usb3000"));
	if(pModule == NULL)  TerminateApplication(" Module Interface --> Bad\n");
	else printf(" Module Interface --> OK\n");

	// попробуем обнаружить модуль USB3000 в первых 127 виртуальных слотах
	for(i = 0x0; i < MaxVirtualSoltsQuantity; i++) if(pModule->OpenDevice(i)) break;
	// что-нибудь обнаружили?
	if(i == MaxVirtualSoltsQuantity) TerminateApplication(" Can't find module USB3000 in first 127 virtual slots!\n");
	else printf(" OpenDevice(%u) --> OK\n", i);

	// прочитаем название обнаруженного модуля
	if(!pModule->GetModuleName(ModuleName)) TerminateApplication(" GetModuleName() --> Bad\n");
	else printf(" GetModuleName() --> OK\n");
	// проверим, что это 'USB3000'
	if(strcmp(ModuleName, "USB3000")) TerminateApplication(" The module is not 'USB3000'\n");
	else printf(" The module is 'USB3000'\n");

	// узнаем текущую скорость работы шины USB20
	if(!pModule->GetUsbSpeed(&UsbSpeed)) { printf(" GetUsbSpeed() --> Bad\n"); exit(1); }
	else printf(" GetUsbSpeed() --> OK\n");
	// теперь отобразим версию драйвера AVR
	printf(" USB Speed is %s\n", UsbSpeed ? "HIGH (480 Mbit/s)" : "FULL (12 Mbit/s)");

	// прочитаем серийный номер модуля
	if(!pModule->GetModuleSerialNumber(ModuleSerialNumber)) TerminateApplication(" GetModuleSerialNumber() --> Bad\n");
	else printf(" GetModuleSerialNumber() --> OK\n");
	// теперь отобразим серийный номер модуля
	printf(" Module Serial Number is %s\n", ModuleSerialNumber);

	// прочитаем версию драйвера AVR
	if(!pModule->GetAvrVersion(AvrVersion)) TerminateApplication(" GetAvrVersion() --> Bad\n");
	else printf(" GetAvrVersion() --> OK\n");
	// теперь отобразим версию драйвера AVR
	printf(" Avr Driver Version is %s\n", AvrVersion);

	// прочитаем ППЗУ
	fi.size = sizeof(RTUSB3000::FLASH);
	if(!pModule->GET_FLASH(&fi)) TerminateApplication(" GET_FLASH() --> Bad\n");
	else printf(" GET_FLASH() --> OK\n");

	// код драйвера DSP возьмём из соответствующего ресурса штатной DLL библиотеки
	if(!pModule->LOAD_DSP()) TerminateApplication(" LOAD_DSP() --> Bad\n");
	else printf(" LOAD_DSP() --> OK\n");

	// проверим загрузку модуля
 	if(!pModule->MODULE_TEST()) TerminateApplication(" MODULE_TEST() --> Bad\n");
	else printf(" MODULE_TEST() --> OK\n");

	// получим информацию об загруженном драйвере DSP
	if(!pModule->GET_DSP_INFO(&di)) TerminateApplication(" GET_DSP_INFO() --> Bad\n");
	else printf(" GET_DSP_INFO() --> OK\n");
	// теперь отобразим версию загруженного драйвера DSP
	printf(" DSP Driver version is %1u.%1u\n", di.DspMajor, di.DspMinor);

	// выведем нулевой отсчёт на первый канал ЦАП
	DacSample = 0x0;
	// откалибруем отсчёт для первого канала
	DacSample = Round((DacSample + fi.DacOffsetCoef[0])*fi.DacScaleCoef[0]);
	if(!pModule->WRITE_SAMPLE(0x0, &DacSample)) TerminateApplication(" WRITE_SAMPLE(0) --> Bad\n");
	else printf(" WRITE_SAMPLE(0) --> OK\n");

	// также нулевой отсчёт выведем на второй канал ЦАП
	DacSample = 0x0;
	// откалибруем отсчёт для второго канала
	DacSample = Round((DacSample + fi.DacOffsetCoef[1])*fi.DacScaleCoef[1]);
	if(!pModule->WRITE_SAMPLE(0x1, &DacSample)) TerminateApplication(" WRITE_SAMPLE(1) --> Bad\n");
	else printf(" WRITE_SAMPLE(1) --> OK\n");

	// прочитаем текущие параметры вывода данных
	dp.size = sizeof(RTUSB3000::OUTPUT_PARS);
	if(!pModule->GET_OUTPUT_PARS(&dp)) TerminateApplication(" GET_OUTPUT_PARS() --> Bad\n");
	else printf(" GET_OUTPUT_PARS() --> OK\n");

	// установим желаемые параметры вывода данных на модуль USB3000
	dp.OutputRate = WriteRate;		  			// частота вывода данных в кГц
	dp.OutputFifoBaseAddress = 0x3000;   	// базовый адрес FIFO буфера вывода
	dp.OutputFifoLength = 0xF80;				// длина FIFO буфера вывода

	// установим требуемые параметры вывода данных
	if(!pModule->SET_OUTPUT_PARS(&dp)) TerminateApplication(" SET_OUTPUT_PARS() --> Bad\n");
	else printf(" SET_OUTPUT_PARS() --> OK\n");

	// отобразим на экране монитора параметры работы модуля по выводу данных 
	printf(" \n");
	printf(" Module USB3000 (S/N %s) is ready ... \n", ModuleSerialNumber);
	printf("  Ouput parameters:\n");
	printf("    WriteRate = %6.1f kHz\n", dp.OutputRate);
	printf("  Signal parameters:\n");
	printf("    SignalFrequency  = %2.2f kHz\n", SignalFrequency);
	printf("    SignalAmplitude  = %1.3f V\n", SignalAmplitude*5.0/2000.0);

	// сбросим флаг ошибок потока ввода данных
	ThreadErrorNumber = 0x0;

	// попробуем выделить память под буфер для выводимых с модуля данных
	WriteBuffer = new SHORT[WritePoints];
	if(!WriteBuffer) TerminateApplication(" Cannot allocate memory for data buffer \n");

	// Создаем и запускаем поток вывода данных из РС в модуль
	hWriteThread = CreateThread(0, 0x2000, ServiceWriteThread, 0x0, 0x0, &WriteTid);
	if(!hWriteThread) TerminateApplication("Cann't start output data thread!");

	// ждем завершения работы нужного потока
	printf("\n Now SINUS signal is on the %s DAC channel\n", DacNumber ? "second" : "first");
	printf(" (you can press any key to terminate the program)\n\n");
	while(!IsThreadComplete)
	{
		if(OldCounter != Counter) { printf(" Counter %3u\r", Counter); OldCounter = Counter; }
		else Sleep(0);
	}

	// ждём окончания работы потока вывода данных
	WaitForSingleObject(hWriteThread, INFINITE);
	// две пустые строчки
	printf("\n\n");

	// если была ошибка - сообщим об этом
	if(ThreadErrorNumber) { TerminateApplication(NULL, false); ShowThreadErrorMessage(); }
	else { printf("\n"); TerminateApplication("\n The program was completed successfully!!!\n", false); }
}

//------------------------------------------------------------------------
// Поток в котором осуществляется вывод данных из РС в модуль
//------------------------------------------------------------------------
DWORD WINAPI ServiceWriteThread(PVOID /*Context*/)
{
	WORD RequestNumber;
	DWORD i;
	DWORD BaseIndex;
	// идентификатор массива их двух событий
	HANDLE WriteEvent[2];
	// массив OVERLAPPED структур из двух элементов
	OVERLAPPED WriteOv[2];
	DWORD BytesTransferred[2];
	DWORD TimeOut;

	// формируем данные для целого FIFO буфера вывода в модуле (учитывая корректировку)
	for(i = 0x0; i < (DWORD)dp.OutputFifoLength; i++)
	{
   	WriteBuffer[i] = Round((2047.0 + SignalAmplitude*sin(2.*M_PI*SignalFrequency*CurrentTime) + fi.DacOffsetCoef[DacNumber])*fi.DacScaleCoef[DacNumber]);
		WriteBuffer[i] &= (WORD)(0xFFF);
		WriteBuffer[i] |= (WORD)(DacNumber << 15) | (WORD)(0x1 << 14);
		CurrentTime += 1.0/dp.OutputRate;
	}
	// заполняем целиком FIFO буфер вывода в DSP модуля
	if(!pModule->PUT_DM_ARRAY(dp.OutputFifoBaseAddress, dp.OutputFifoLength, (SHORT *)WriteBuffer))
   										{ ThreadErrorNumber = 0x1; IsThreadComplete = true; return 1; }

	// теперь формируем выводимые данные для всего буфера WriteBuffer (учитывая корректировку)
	for(i = 0x0; i < 2*DataStep; i++)
	{
		WriteBuffer[i] = Round((2047.0 + SignalAmplitude*sin(2.*M_PI*SignalFrequency*CurrentTime) + fi.DacOffsetCoef[DacNumber])*fi.DacScaleCoef[DacNumber]);
		WriteBuffer[i] &= (WORD)(0xFFF);
		WriteBuffer[i] |= (WORD)(DacNumber << 15) | (WORD)(0x1 << 14);
		CurrentTime += 1.0/dp.OutputRate;
	}

	// остановим вывод данных и одновременно прочистим соответствующий канал bulk USB (PIPE_RESET)
	if(!pModule->STOP_WRITE()) { ThreadErrorNumber = 0x6; IsThreadComplete = true; return 0; }

	// создадим два события
	WriteEvent[0] = CreateEvent(NULL, FALSE , FALSE, NULL);
	memset(&WriteOv[0], 0, sizeof(OVERLAPPED)); WriteOv[0].hEvent = WriteEvent[0];
	WriteEvent[1] = CreateEvent(NULL, FALSE , FALSE, NULL);
	memset(&WriteOv[1], 0, sizeof(OVERLAPPED)); WriteOv[1].hEvent = WriteEvent[1];

	// таймаут вывода данных
	TimeOut = (DWORD)(DataStep/dp.OutputRate + 1000);

	// делаем предварительный запрос на вывод данных
	RequestNumber = 0x0;
	if(!pModule->WriteData(WriteBuffer, &DataStep, &BytesTransferred[RequestNumber], &WriteOv[RequestNumber]))
				if(GetLastError() != ERROR_IO_PENDING) { CloseHandle(WriteEvent[0]); CloseHandle(WriteEvent[1]); ThreadErrorNumber = 0x2; IsThreadComplete = true; return 0; }

	// теперь запускаем собственно сам вывод данных
	if(pModule->START_WRITE())
	{
		// цикл перманентного вывода данных
		for(;;)
		{
			RequestNumber ^= 0x1;
			// сделаем запрос на вывод очередной порции данных в DSP модуля
			if(!pModule->WriteData(WriteBuffer + RequestNumber*DataStep, &DataStep, &BytesTransferred[RequestNumber], &WriteOv[RequestNumber]))
					if(GetLastError() != ERROR_IO_PENDING) { ThreadErrorNumber = 0x2; break; }

			// ждём окончания операции вывода очередной порции данных
			if(WaitForSingleObject(WriteEvent[RequestNumber^0x1], TimeOut) == WAIT_TIMEOUT)
				            		{ ThreadErrorNumber = 0x3; break; }

			// сформируем следующую порцию выводимых данных (учитывая корректировку)
			BaseIndex = (RequestNumber^0x1)*DataStep;
			for(i = 0x0; i < DataStep; i++)
			{
				WriteBuffer[i + BaseIndex] = Round((2047.0 + SignalAmplitude*sin(2.*M_PI*SignalFrequency*CurrentTime) + fi.DacOffsetCoef[DacNumber])*fi.DacScaleCoef[DacNumber]);
				WriteBuffer[i + BaseIndex] &= (WORD)(0xFFF);
				WriteBuffer[i + BaseIndex] |= (WORD)(DacNumber << 15) | (WORD)(0x1 << 14);
				CurrentTime += 1.0/dp.OutputRate;
	  		}

			if(ThreadErrorNumber) break;
			else if(kbhit()) { ThreadErrorNumber = 0x1; break; }
			else Sleep(0);
			Counter++;
		}
	}
	else { ThreadErrorNumber = 0x5; }

	// остановим вывод данных
	if(!pModule->STOP_WRITE()) ThreadErrorNumber = 0x6;
	// уберём за собой
	if(!CancelIo(pModule->GetModuleHandle())) ThreadErrorNumber = 0x7;
	// освободим идентификаторы событий
	CloseHandle(WriteEvent[0]); CloseHandle(WriteEvent[1]);

	// установим флажок окончания потока вывода данных
	IsThreadComplete = true;

	return 0;							// Выйдем из потока
}

//---------------------------------------------------------------------------
//
//---------------------------------------------------------------------------
WORD Round(double Data)
{
	if(Data > 0.0) Data += 0.5;
	else if(Data < 0.0) Data = -0.5;
	return (WORD)Data;
}


//------------------------------------------------------------------------
// Отобразим сообщение с ошибкой
//------------------------------------------------------------------------
void ShowThreadErrorMessage(void)
{
	switch(ThreadErrorNumber)
	{
		case 0x0:
			break;

		case 0x1:
			// если программа была злобно прервана, предъявим ноту протеста
			printf("\n WRITE Thread: The program was terminated! :(((\n");
			break;

		case 0x2:
			printf("\n WRITE Thread: WriteData() --> Bad :(((\n");
			break;

		case 0x3:
			printf("\n WRITE Thread: Timeout is occured :(((\n");
			break;

		case 0x4:
			printf("\n WRITE Thread: Buffer Data Error! :(((\n");
			break;

		case 0x5:
			printf("\n WRITE Thread: START_WRITE() --> Bad :(((\n");
			break;

		case 0x6:
			printf("\n WRITE Thread: STOP_WRITE() --> Bad! :(((\n");
			break;

		case 0x7:
			printf("\n READ Thread: Can't complete input and output (I/O) operations! :(((");
			break;

		default:
			printf("\n WRITE Thread: Unknown error! :(((\n");
			break;
	}

	return;
}

//------------------------------------------------------------------------
// вывод сообщения и, если нужно, аварийный выход из программы
//------------------------------------------------------------------------
void TerminateApplication(char *ErrorString, bool TerminationFlag)
{
	// подчищаем интерфейс модуля
	if(pModule)
	{ 
		// освободим интерфейс модуля
		if(!pModule->ReleaseInstance()) printf(" ReleaseInstance() --> Bad\n"); 
		else printf(" ReleaseInstance() --> OK\n");
		// обнулим указатель на интерфейс модуля
		pModule = NULL; 
	}

	// освобождаем занятые ресурсы
	if(WriteBuffer) { delete[] WriteBuffer; WriteBuffer = NULL; }
	// освободим идентификатор потока вывода данных
	if(hWriteThread) { CloseHandle(hWriteThread); hWriteThread = NULL; }

	// выводим текст сообщения
	if(ErrorString) printf(ErrorString);

	// если нужно - аварийно завершаем программу
	if(TerminationFlag) exit(1);
	else return;
}
