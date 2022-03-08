import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Card, CardContent, CardHeader } from '@mui/material';
import { AbstractSection, SectionProps } from '../common';


interface PerformanceRow {
    fee:number;
    investment:number;
    value:number;
    profit:number;
}

interface PerformanceData {
    [year:number]:{[ticker:string]:PerformanceRow}
}

interface PerformanceState {
    data:PerformanceData;
}

interface PerformanceProps {}

export class Performance extends AbstractSection<PerformanceProps, PerformanceState> {

    sectionName = () => 'Performance';

    constructor(props: PerformanceProps & SectionProps) {
        super(props);
        this.state = {
            data: {},
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadPerformance().then(() =>
            this.props.displayProgressBar(false)
        );
    }

    loadPerformance() {
        return fetch('/performance/get')
            .then<PerformanceData>(res => res.json())
            .then(data => {
                this.setState({data});
            });
    }

    render() {
        return (
            <Box>
                {Object.entries(this.state.data).map(([year, data]) =>
                    <Card elevation={3} sx={{marginBottom: '1em'}}>
                        <CardHeader title={year} />
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Ticker</TableCell>
                                            <TableCell align='right'>Investment</TableCell>
                                            <TableCell align='center'>Value</TableCell>
                                            <TableCell align='right'>Fee</TableCell>
                                            <TableCell colSpan={2} align='center'>Profit</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {Object.entries<PerformanceRow>(data).map(([ticker, d], i) =>
                                            <TableRow key={i}>
                                                <TableCell>{ticker}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.investment)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.value)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.fee)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.profit)}</TableCell>
                                                <TableCell align='right'>{this.formatPercents(d.profit/d.investment)}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                )}
            </Box>
        )
    }
}