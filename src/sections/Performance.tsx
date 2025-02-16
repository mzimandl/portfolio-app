import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Card, CardContent, CardHeader, FormGroup, Switch, FormControlLabel } from '@mui/material';
import { AbstractSection, SectionProps } from '../common';


interface PerformanceRow {
    investment_change:number;
    value_change:number;
    profit_change:number;
    fee_change:number;
    return_change:number;
    investment_total:number;
    value_total:number;
    profit_total:number;
    fee_total:number;
    return_total:number;
}

interface PerformanceData {
    [year:number]:{[ticker:string]:PerformanceRow}
}

interface PerformanceState {
    data:PerformanceData;
    years:Array<number>;
    tickers:Array<string>;
    detailedView:boolean;
}

interface PerformanceProps {}

export class Performance extends AbstractSection<PerformanceProps, PerformanceState> {

    sectionName = () => 'Performance';

    constructor(props: PerformanceProps & SectionProps) {
        super(props);
        this.state = {
            data: {},
            years: [],
            tickers: [],
            detailedView: false,
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
                this.setState({
                    data,
                    years: Object.keys(data).map(v => parseInt(v)).sort(),
                    tickers: Object.values(data).reduce(
                        (acc, curr) => {
                            Object.keys(curr).forEach(ticker => {
                                if (!acc.includes(ticker)) {
                                    acc.push(ticker);
                                }
                            })
                            return acc
                        },
                        []
                    ).sort()
                });
            });
    }

    render() {
        return <Box>
            <FormGroup>
                <FormControlLabel control={<Switch checked={this.state.detailedView} onChange={(e, value) => this.setState({detailedView: value})}/>} label="Detailed view" />
            </FormGroup>

            { this.state.detailedView ?
                Object.entries(this.state.data).map(([year, data], i) =>
                    <Card key={i} elevation={3} sx={{marginBottom: '1em'}}>
                        <CardHeader title={year} />
                        <CardContent>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Ticker</TableCell>
                                            <TableCell align='right'>Investment</TableCell>
                                            <TableCell align='right'>Value</TableCell>
                                            <TableCell align='right'>Return</TableCell>
                                            <TableCell align='right'>Fee</TableCell>
                                            <TableCell colSpan={2} align='center'>Profit</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {Object.entries<PerformanceRow>(data).map(([ticker, d], i) =>
                                            <TableRow key={i}>
                                                <TableCell>{ticker}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.investment_change)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.value_change, {signed: true})}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.return_change)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.fee_change)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(d.profit_change, {signed: true})}</TableCell>
                                                <TableCell align='left'>{this.formatPercents((d.profit_change)/(d.investment_change+d.value_total-d.value_change), {signed: true})}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                ) :
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell></TableCell>
                                {this.state.years.map(year =>
                                    <TableCell key={year} align='center'>{year}</TableCell>
                                )}
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {this.state.tickers.map(ticker =>
                                <TableRow key={ticker}>
                                    <TableCell>{ticker}</TableCell>
                                    {this.state.years.map(year => {
                                        const d = this.state.data[year][ticker];
                                        return <TableCell key={year} align='center'>
                                            {d ? this.formatPercents((d.profit_change)/(d.investment_change+d.value_total-d.value_change), {signed: true}) : null}
                                        </TableCell>
                                    })}
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            }
        </Box>
    }
}