using System;
using System.Text;
using System.Threading;
using System.Net;
using System.Net.Sockets;

namespace AsyncClient
{
    // State object for receiving data from remote device.  
    public class StateObject
    {
        // Client socket.  
        public Socket workSocket = null;
        // Size of receive buffer.  
        public const int BufferSize = 256;
        // Receive buffer.  
        public byte[] buffer = new byte[BufferSize];
        // Received data string.  
        public StringBuilder sb = new StringBuilder();
    }

    public class AsyncClient
    {
        // The TCP_PORT number for the remote device.  
        private const int TCP_PORT = 10000;

        // ManualResetEvent instances signal completion.  
        private static ManualResetEvent connectDone = new ManualResetEvent(false);
        private static ManualResetEvent sendDone = new ManualResetEvent(false);
        private static ManualResetEvent receiveDone = new ManualResetEvent(false);

        // The response from the remote device.  
        private static String response = String.Empty;
        private const bool DEPLOY_ON_WINDOW = false;

        private static void StartTCPClient()
        {
            try
            {
                // Establish the remote endpoint for the socket.  
                IPAddress ipAddress = IPAddress.Parse(DEPLOY_ON_WINDOW ? "192.168.25.161" : "127.0.0.1");
                IPEndPoint remoteEP = new IPEndPoint(ipAddress, TCP_PORT);

                // Create a TCP/IP socket.  
                
                Socket client = new Socket(ipAddress.AddressFamily, SocketType.Stream, ProtocolType.Tcp);

                // Console.WriteLine("ip address is {0} address family is {1}", ipAddress.ToString(), ipAddress.AddressFamily.ToString());
                // Console.WriteLine("remote ep is {0}", remoteEP.ToString());
                // Connect to the remote endpoint.  
                client.BeginConnect(remoteEP, new AsyncCallback(ConnectCallback), client);
                connectDone.WaitOne();

                // Send test data to the remote device.  
                Send(client, "CCS is ready");
                sendDone.WaitOne();

                StateObject state = new StateObject() { workSocket = client };
                while (true)
                {
                    receiveDone.Reset();
                    // Receive(client);
                    client.BeginReceive(state.buffer, 0, StateObject.BufferSize, 0, new AsyncCallback(ReceiveCallback), state);
                    receiveDone.WaitOne();

                    /*
                    sendDone.Reset();
                    // Receive(client);
                    client.BeginSend(state.buffer, 0, StateObject.BufferSize, 0, new AsyncCallback(ReceiveCallback), state);
                    sendDone.WaitOne();
                    */
                }

                // Receive the response from the remote device.  

                // Write the response to the console.  

                // Release the socket.  
                // client.Shutdown(SocketShutdown.Both);
                client.Shutdown(SocketShutdown.Both);
                client.Close();

            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
            }
        }

        private static void ConnectCallback(IAsyncResult ar)
        {
            try
            {
                // Retrieve the socket from the state object.  
                Socket client = (Socket)ar.AsyncState;

                // Complete the connection.  
                client.EndConnect(ar);

                Console.WriteLine("Socket connected to {0}", client.RemoteEndPoint.ToString());

                // Signal that the connection has been made.  
                connectDone.Set();
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
            }
        }

        private static void Receive(Socket client)
        {
            try
            {
                // Create the state object.  
                StateObject state = new StateObject();
                state.workSocket = client;

                // Begin receiving the data from the remote device.  
                client.BeginReceive(state.buffer, 0, StateObject.BufferSize, 0, new AsyncCallback(ReceiveCallback), state);
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
            }
        }

        private static void ReceiveCallback(IAsyncResult ar)
        {
            try
            {
                // Retrieve the state object and the client socket from the asynchronous state object.  
                StateObject state = (StateObject)ar.AsyncState;
                Socket client = state.workSocket;

                int bytesRead = client.EndReceive(ar);
                if (bytesRead > 0)
                {
                    state.sb.Append(Encoding.ASCII.GetString(state.buffer, 0, bytesRead));
                    // Check if there is anymore data on the socket
                    if (client.Available > 0)
                    {
                        client.BeginReceive(state.buffer, 0, StateObject.BufferSize, 0, new AsyncCallback(ReceiveCallback), state);
                    }
                }

                if (bytesRead == 0 || client.Available == 0)
                {
                    if (state.sb.Length > 1)
                    {
                        response = state.sb.ToString();
                        Console.WriteLine(response);
                        state.sb.Clear();
                    }
                    receiveDone.Set();
                }
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
            }
        }

        private static void Send(Socket client, String data)
        {
            // Convert the string data to byte data using ASCII encoding.  
            byte[] byteData = Encoding.ASCII.GetBytes(data);

            // Begin sending the data to the remote device.  
            client.BeginSend(byteData, 0, byteData.Length, 0, new AsyncCallback(SendCallback), client);
        }

        private static void SendCallback(IAsyncResult ar)
        {
            try
            {
                // Retrieve the socket from the state object.  
                Socket client = (Socket)ar.AsyncState;

                // Complete sending the data to the remote device.  
                int bytesSent = client.EndSend(ar);
                Console.WriteLine("Sent {0} bytes to server.", bytesSent);

                // Signal that all bytes have been sent.  
                sendDone.Set();
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
            }
        }
        public static int Main(String[] args)
        {
            StartTCPClient();
            return 0;
        }
    }

}
