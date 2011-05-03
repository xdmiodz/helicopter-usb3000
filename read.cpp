//******************************************************************************
//���������� ��������� ��� ����� ������ � �� �� ������ USB3000
//******************************************************************************
#include <stdio.h>
#include <conio.h>
#include <math.h>
#include "Rtusbapi.h"

// ��������� ���������� ���������
void TerminateApplication(char *ErrorString, bool TerminationFlag = true);
// �������� ���������� ���������� ������� �� ���� ������
bool WaitingForRequestCompleted(OVERLAPPED *ReadOv);
// ����������� ������ ���������� ���������
void ShowThreadErrorMessage(void);

// ������� ������ ����� ������ � ������
DWORD 	WINAPI ServiceReadThread(PVOID /*Context*/);
// ������������� ������ �����
HANDLE 	hReadThread;
DWORD 	ReadTid;

// ������������� ����� ��� ������ ���������� ������
HANDLE hFile;

// ������� ������ ���������� Rtusbapi.dll
DWORD DllVersion;
// ��������� �� ��������� ������
IRTUSB3000 *pModule;
// ����� ������
HANDLE ModuleHandle;
// �������� ������
char ModuleName[10];
// �������� ������ ���� USB
BYTE UsbSpeed;
// �������� ����� ������
char ModuleSerialNumber[9];
// ������ �������� AVR
char AvrVersion[5];
// ���������, ���������� ���������� � ������ �������� DSP
RTUSB3000::DSP_INFO di;
// ��������� ���������� � ���� ������
RTUSB3000::FLASH fi;
// ��������� ���������� ������ ���
RTUSB3000::INPUT_PARS ip;

// ����������� ��������� ���-�� ������������ ����������� ������
const WORD MaxVirtualSoltsQuantity = 127;
// �������  ����� ������
const double ReadRate = 3000.0;

//max ��������� ���-�� ������������ �������� (������� 32) ��� �. ReadData � WriteData()
DWORD DataStep = 1024*1024;
// ������� ������ �� DataStep �������� ����� ������� � ����
const WORD NBlockRead = 20;
// ��������� �� ����� ��� �������� ������
SHORT	*ReadBuffer;

// �������� �������-���������
DWORD Counter = 0x0, OldCounter = 0xFFFFFFFF;

// ����� ������ ��� ���������� ������ ����� ������
WORD ThreadErrorNumber;
// ������ ���������� ������� ����� ������
bool IsThreadComplete = false;


//------------------------------------------------------------------------
// �������� ���������
//------------------------------------------------------------------------
void main(int argc, char* argv[])
{
  WORD i;
  char* savefile = argv[1];
  WORD channel1 = atoi(argv[2]);
  WORD channel2 = atoi(argv[3]);

	// �������� ����� ��������	
	system("cls");

	printf(" **********************************************\n");
	printf(" Data Reading Console Example for USB3000 unit \n");
	printf(" **********************************************\n\n");

	// �������� ������ ������������ ���������� Rtusbapi.dll
	if((DllVersion = RtGetDllVersion()) != CURRENT_VERSION_RTUSBAPI) 
	{	
		char String[128];
		sprintf(String, " Rtusbapi.dll Version Error!!!\n   Current: %1u.%1u. Required: %1u.%1u",
											DllVersion >> 0x10, DllVersion & 0xFFFF,
											CURRENT_VERSION_RTUSBAPI >> 0x10, CURRENT_VERSION_RTUSBAPI & 0xFFFF);
		
		TerminateApplication(String);
	}		
	else printf(" Rtusbapi.dll Version --> OK\n");

	// ������� ��������� �� ��������� ������ USB3000
	pModule = static_cast<IRTUSB3000 *>(RtCreateInstance("usb3000"));
	if(!pModule) TerminateApplication(" Module Interface --> Bad\n");
	else printf(" Module Interface --> OK\n");

	// ��������� ���������� ������ USB3000 � ������ 127 ����������� ������
	for(i = 0x0; i < MaxVirtualSoltsQuantity; i++) if(pModule->OpenDevice(i)) break;
	// ���-������ ����������?
	if(i == MaxVirtualSoltsQuantity) TerminateApplication(" Can't find module USB3000 in first 127 virtual slots!\n");
	else printf(" OpenDevice(%u) --> OK\n", i);

	// ��������� �������� ���������� (handle) ����������
	ModuleHandle = pModule->GetModuleHandle();
	if(ModuleHandle == INVALID_HANDLE_VALUE) TerminateApplication(" GetModuleHandle() --> Bad\n");
	else printf(" GetModuleHandle() --> OK\n");

	// ��������� �������� ������������� ������
	if(!pModule->GetModuleName(ModuleName)) TerminateApplication(" GetModuleName() --> Bad\n");
	else printf(" GetModuleName() --> OK\n");

	// ��������, ��� ��� 'USB3000'
	if(strcmp(ModuleName, "USB3000")) TerminateApplication(" The module is not 'USB3000'\n");
	else printf(" The module is 'USB3000'\n");

	// ������ ������� �������� ������ ���� USB20
	if(!pModule->GetUsbSpeed(&UsbSpeed)) TerminateApplication(" GetUsbSpeed() --> Bad\n");
	else printf(" GetUsbSpeed() --> OK\n");
	// ������ ��������� ������ �������� AVR
	printf(" USB Speed is %s\n", UsbSpeed ? "HIGH (480 Mbit/s)" : "FULL (12 Mbit/s)");

	// ��������� �������� ����� ������
	if(!pModule->GetModuleSerialNumber(ModuleSerialNumber)) TerminateApplication(" GetModuleSerialNumber() --> Bad\n");
	else printf(" GetModuleSerialNumber() --> OK\n");
	// ������ ��������� �������� ����� ������
	printf(" Module Serial Number is %s\n", ModuleSerialNumber);

	// ��������� ������ �������� AVR
	if(!pModule->GetAvrVersion(AvrVersion)) TerminateApplication(" GetAvrVersion() --> Bad\n");
	else printf(" GetAvrVersion() --> OK\n");
	// ������ ��������� ������ �������� AVR
	printf(" Avr Driver Version is %s\n", AvrVersion);

	// ��� �������� DSP ������ �� ���������������� ������� ������� DLL ����������
	if(!pModule->LOAD_DSP()) TerminateApplication(" LOAD_DSP() --> Bad\n");
	else printf(" LOAD_DSP() --> OK\n");

	// �������� �������� ������
 	if(!pModule->MODULE_TEST()) TerminateApplication(" MODULE_TEST() --> Bad\n");
	else printf(" MODULE_TEST() --> OK\n");

	// ������� ������ ������������ �������� DSP
	if(!pModule->GET_DSP_INFO(&di)) TerminateApplication(" GET_DSP_VERSION() --> Bad\n");
	else printf(" GET_DSP_VERSION() --> OK\n");
	// ������ ��������� ������ ������������ �������� DSP
	printf(" DSP Driver version is %1u.%1u\n", di.DspMajor, di.DspMinor);

	// ����������� ����������������� ���� size ��������� RTUSB3000::FLASH
	fi.size = sizeof(RTUSB3000::FLASH);
	// ������� ���������� �� ���� ������
	if(!pModule->GET_FLASH(&fi)) TerminateApplication(" GET_MODULE_DESCR() --> Bad\n");
	else printf(" GET_MODULE_DESCR() --> OK\n");

	// ����������� ����������������� ���� size ��������� RTUSB3000::INPUT_PARS
	ip.size = sizeof(RTUSB3000::INPUT_PARS);
	// ������� ������� ��������� ������ ���
	if(!pModule->GET_INPUT_PARS(&ip)) TerminateApplication(" GET_INPUT_PARS() --> Bad\n");
	else printf(" GET_INPUT_PARS() --> OK\n");

	// ��������� �������� ��������� ���
	ip.CorrectionEnabled = true;				// �������� ������������� �������� ������
	ip.InputClockSource = RTUSB3000::INTERNAL_INPUT_CLOCK;	// ����� ������������ ���������� �������� �������� ��� ����� ������
//	ip.InputClockSource = RTUSB3000::EXTERNAL_INPUT_CLOCK;	// ����� ������������ ������� �������� �������� ��� ����� ������
	ip.SynchroType = RTUSB3000::NO_SYNCHRO;	// �� ����� ������������ ������� ������������� ��� ����� ������  
//	ip.SynchroType = RTUSB3000::TTL_START_SYNCHRO;	// ����� ������������ �������� ������������� ������ ��� ����� ������  
	ip.ChannelsQuantity = 0x2;					// ������ �������� ������
	//for(i = 0x0; i < ip.ChannelsQuantity; i++) ip.ControlTable[i] = (WORD)(i);
	ip.ControlTable[0] = (WORD)(channel1);
	ip.ControlTable[1] = (WORD)(channel2);
	ip.InputRate = ReadRate;					// ������� ������ ��� � ���
	ip.InterKadrDelay = 0.0;					// ����������� �������� - ���� ������ ������������� � 0.0
	ip.InputFifoBaseAddress = 0x0;  			// ������� ����� FIFO ������ ���
	ip.InputFifoLength = 0x3000;	 			// ����� FIFO ������ ���
	// ����� ������������ ��������� ������������� ������������, ������� ��������� � ���� ������
	for(i = 0x0; i < 8; i++) { ip.AdcOffsetCoef[i] = fi.AdcOffsetCoef[i]; ip.AdcScaleCoef[i] = fi.AdcScaleCoef[i]; }
	// ��������� ��������� ��������� ������ ��� � ������
	if(!pModule->SET_INPUT_PARS(&ip)) TerminateApplication(" SET_INPUT_PARS() --> Bad\n");
	else printf(" SET_INPUT_PARS() --> OK\n");

	// ��������� �� ������ ������� ��������� ������ ������ USB3000
	printf(" \n");
	printf(" Module USB3000 (S/N %s) is ready ... \n", ModuleSerialNumber);
	printf(" Adc parameters:\n");
	printf("   InputClockSource is %s\n", ip.InputClockSource ? "EXTERNAL" : "INTERNAL");
	printf("   SynchroType is %s\n", ip.SynchroType ? "TTL_START_SYNCHRO" : "NO_SYNCHRO");
	printf("   ChannelsQuantity = %2d\n", ip.ChannelsQuantity);
	printf("   AdcRate = %8.3f kHz\n", ip.InputRate);
	printf("   InterKadrDelay = %2.4f ms\n", ip.InterKadrDelay);
	printf("   ChannelRate = %8.3f kHz\n", ip.ChannelRate);

	// ���� �������� ����� ��� :(
	hFile = INVALID_HANDLE_VALUE;
	// ������� ���� ������ ������ ����� ������
	ThreadErrorNumber = 0x0;

	// ��������� �������� ������ ��� ����� ��� �������� � ������ ������
	ReadBuffer = new SHORT[NBlockRead * DataStep];
	if(!ReadBuffer) TerminateApplication(" Cannot allocate memory for ReadBuffer\n");

	// ������� � ��������� ����� ����� ����� ������ �� ������
	hReadThread = CreateThread(0, 0x2000, ServiceReadThread, 0, 0, &ReadTid);
	if(!hReadThread) TerminateApplication("Cann't start input data thread!");

	// ���� ���������� ������ ������� ������
	printf("\n");
	while(!IsThreadComplete)
	{
		if(OldCounter != Counter) { printf(" Counter %3u from %3u\r", Counter, NBlockRead); OldCounter = Counter; }
		else Sleep(20);
	}

	// ��� ��������� ������ ������ ����� ������
	WaitForSingleObject(hReadThread, INFINITE);
	// ��� ������ �������
	printf("\n\n");

	// ���� �� ���� ������ ����� ������ - ������� ���������� ������ � ����
 	if(!ThreadErrorNumber)
	{
		// ������� ���� ��� ������ ���������� ������
		hFile = CreateFile(savefile, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
		if(hFile == INVALID_HANDLE_VALUE) TerminateApplication(" Open file --> Failed!!!\n");
		else printf(" CreateFile --> Ok\n");

		// ������ ������� � ���� ���������� ������
		DWORD FileBytesWritten = 0x0;
		if(!WriteFile(	hFile,							// handle to file to write to
	    					ReadBuffer,						// pointer to data to write to file
							2*NBlockRead*DataStep,		// number of bytes to write
    						&FileBytesWritten,			// pointer to number of bytes written
					   	NULL			  					// pointer to structure needed for overlapped I/O
					   ))  TerminateApplication(" WriteFile --> Failed!!!");
		else printf(" WriteFile --> Ok\n");
	}		

	// ���� ���� ������ - ������� �� ����
	if(ThreadErrorNumber) { TerminateApplication(NULL, false); ShowThreadErrorMessage(); }
	else { printf("\n"); TerminateApplication("\n The program was completed successfully!!!\n", false); }
}

//------------------------------------------------------------------------
// ����� � ������� �������������� ���� ������ � �� �� ������
//------------------------------------------------------------------------
DWORD WINAPI ServiceReadThread(PVOID /*Context*/)
{
	WORD i;
	// ����� ������� �� ���� ������
	WORD RequestNumber;
	// ������������� ������� �� ���� �������
	HANDLE ReadEvent[2];
	// ������ OVERLAPPED �������� �� ���� ���������
	OVERLAPPED ReadOv[2];
	DWORD BytesTransferred[2];
//	DWORD TimeOut;

	// ��������� ���� ������ � ������������ ��������� ��������������� ����� bulk USB
	if(!pModule->STOP_READ()) { ThreadErrorNumber = 0x6; IsThreadComplete = true; return 0; }

	// �������� ��� �������
	ReadEvent[0] = CreateEvent(NULL, FALSE , FALSE, NULL);
	memset(&ReadOv[0], 0, sizeof(OVERLAPPED)); ReadOv[0].hEvent = ReadEvent[0];
	ReadEvent[1] = CreateEvent(NULL, FALSE , FALSE, NULL);
	memset(&ReadOv[1], 0, sizeof(OVERLAPPED)); ReadOv[1].hEvent = ReadEvent[1];

	// ������� ����� ������
//	TimeOut = (DWORD)(DataStep/ReadRate + 1000);

	// ������ ��������������� ������ �� ���� ������
	RequestNumber = 0x0;
	if(!pModule->ReadData(ReadBuffer, &DataStep, &BytesTransferred[RequestNumber], &ReadOv[RequestNumber]))
				if(GetLastError() != ERROR_IO_PENDING) { CloseHandle(ReadEvent[0]); CloseHandle(ReadEvent[1]); ThreadErrorNumber = 0x2; IsThreadComplete = true; return 0; }

	// ������ ��������� ���� ������
	if(pModule->START_READ())
	{
		// ���� ����� ������
		for(i = 0x1; i < NBlockRead; i++)
		{
			RequestNumber ^= 0x1;
			// ������� ������ �� ��������� ������ ������
			if(!pModule->ReadData(ReadBuffer + i*DataStep, &DataStep, &BytesTransferred[RequestNumber], &ReadOv[RequestNumber]))
					if(GetLastError() != ERROR_IO_PENDING) { ThreadErrorNumber = 0x2; break; }

			// ��� ��������� �������� ����� ��������� ������ ������
			if(!WaitingForRequestCompleted(&ReadOv[RequestNumber^0x1])) break;
//			if(WaitForSingleObject(ReadEvent[!RequestNumber], TimeOut) == WAIT_TIMEOUT)
//				            		{ ThreadErrorNumber = 0x3; break; }

			if(ThreadErrorNumber) break;
			else if(kbhit()) { ThreadErrorNumber = 0x1; break; }
			else Sleep(20);
			Counter++;
		}

		// ��� ��������� �������� ����� ��������� ������ ������ 
		if(!ThreadErrorNumber)
		{
			RequestNumber ^= 0x1;
			WaitingForRequestCompleted(&ReadOv[RequestNumber^0x1]);
//			if(WaitForSingleObject(ReadEvent[!RequestNumber], TimeOut) == WAIT_TIMEOUT) ThreadErrorNumber = 0x3;
			Counter++;
		}
	}
	else { ThreadErrorNumber = 0x5; }

	// ��������� ���� ������
	if(!pModule->STOP_READ()) ThreadErrorNumber = 0x6;
	// ���� ����, �� ������ ������������� ����������� ������
	if(!CancelIo(pModule->GetModuleHandle())) ThreadErrorNumber = 0x7;
	// ��������� ��� �������������� �������
	for(i = 0x0; i < 0x2; i++) CloseHandle(ReadEvent[i]);
	// ��������� ��������
	Sleep(100);
	// ��������� ������ ��������� ������ ����� ������
	IsThreadComplete = true;
	// ������ ����� �������� �� ������ ����� ������
	return 0;
}

//---------------------------------------------------------------------------
//
//---------------------------------------------------------------------------
bool WaitingForRequestCompleted(OVERLAPPED *ReadOv)
{
	DWORD ReadBytesTransferred;

	while(true)
	{
		if(GetOverlappedResult(ModuleHandle, ReadOv, &ReadBytesTransferred, FALSE)) break;
		else if(GetLastError() !=  ERROR_IO_INCOMPLETE) { ThreadErrorNumber = 0x3; return false; }
		else if(kbhit()) { ThreadErrorNumber = 0x1; return false; }
		else Sleep(20);
	}
	return true;
}

//------------------------------------------------------------------------
// ��������� ��������� � �������
//------------------------------------------------------------------------
void ShowThreadErrorMessage(void)
{
	switch(ThreadErrorNumber)
	{
		case 0x0:
			break;

		case 0x1:
			// ���� ��������� ���� ������ ��������, ��������� ���� ��������
			printf("\n READ Thread: The program was terminated! :(((\n");
			break;

		case 0x2:
			printf("\n READ Thread: ReadData() --> Bad :(((\n");
			break;

		case 0x3:
			printf("\n READ Thread: Read Request --> Bad :(((\n");
//			printf("\n READ Thread: Timeout is occured :(((\n");
			break;

		case 0x4:
			printf("\n READ Thread: Buffer Data Error! :(((\n");
			break;

		case 0x5:
			printf("\n READ Thread: START_READ() --> Bad :(((\n");
			break;

		case 0x6:
			printf("\n READ Thread: STOP_READ() --> Bad! :(((\n");
			break;

		case 0x7:
			printf("\n READ Thread: Can't complete input and output (I/O) operations! :(((");
			break;

		default:
			printf("\n READ Thread: Unknown error! :(((\n");
			break;
	}

	return;
}

//------------------------------------------------------------------------
// ����� ��������� �, ���� �����, ��������� ����� �� ���������
//------------------------------------------------------------------------
void TerminateApplication(char *ErrorString, bool TerminationFlag)
{
	// ��������� ��������� ������
	if(pModule)
	{ 
		// ��������� ��������� ������
		if(!pModule->ReleaseInstance()) printf(" ReleaseInstance() --> Bad\n"); 
		else printf(" ReleaseInstance() --> OK\n");
		// ������� ��������� �� ��������� ������
		pModule = NULL; 
	}

	// ����������� ������� �������
	if(ReadBuffer) { delete[] ReadBuffer; ReadBuffer = NULL; }
	// ��������� ������������� ������ ����� ������
	if(hReadThread) { CloseHandle(hReadThread); hReadThread = NULL; }
	// ��������� ������������� ����� ������
	if(hFile != INVALID_HANDLE_VALUE) { CloseHandle(hFile); hFile = INVALID_HANDLE_VALUE; }

	// ������� ����� ���������
	if(ErrorString) printf(ErrorString);

	// ���� ����� - �������� ��������� ���������
	if(TerminationFlag) exit(1);
	else return;
}
